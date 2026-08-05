from __future__ import annotations

import asyncio
import atexit
import hashlib
import html
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Coroutine, Iterable, TypeVar
from urllib.parse import quote

from .models import AudioAsset


class AudioError(RuntimeError):
    pass


_T = TypeVar("_T")


class _AsyncLoopRunner:
    """Run async TTS work on one reusable background loop.

    Gradio callbacks execute in worker threads. Creating and destroying an asyncio
    event loop for every TTS request can produce noisy loop-finalizer errors and is
    especially fragile under concurrent Space traffic. This runner owns exactly
    one daemon loop for the process and submits bounded coroutines to it.
    """

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._run, name="tts-async-loop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise AudioError("The audio worker could not start.")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

    def run(self, coroutine: Coroutine[object, object, _T], timeout_seconds: float) -> _T:
        if self._loop is None or not self._loop.is_running():
            coroutine.close()
            raise AudioError("The audio worker is unavailable.")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            future.cancel()
            raise AudioError("TTS timed out. Your completed work remains saved.") from exc
        except AudioError:
            raise
        except Exception as exc:
            raise AudioError(f"TTS failed: {type(exc).__name__}.") from exc

    def close(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
            self._thread.join(timeout=2)


_RUNNER: _AsyncLoopRunner | None = None
_RUNNER_LOCK = threading.Lock()


def _get_async_runner() -> _AsyncLoopRunner:
    global _RUNNER
    if _RUNNER is None:
        with _RUNNER_LOCK:
            if _RUNNER is None:
                _RUNNER = _AsyncLoopRunner()
    return _RUNNER


def _close_async_runner() -> None:
    global _RUNNER
    if _RUNNER is not None:
        _RUNNER.close()
        _RUNNER = None


atexit.register(_close_async_runner)


def audio_cache_key(
    transcript: str, voice: str, rate: str, engine_version: str, pitch: str = "+0Hz", volume: str = "+0%"
) -> str:
    raw = "\n".join([transcript.strip(), voice.strip(), rate.strip(), pitch.strip(), volume.strip(), engine_version.strip()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_audio_file(path: str | Path, minimum_bytes: int = 512) -> bool:
    target = Path(path)
    return target.exists() and target.is_file() and target.stat().st_size >= minimum_bytes


def audio_duration_seconds(path: str | Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def resolve_audio_path(asset: AudioAsset, project_root: str | Path) -> Path:
    if not asset.path:
        raise AudioError("The selected listening item has no local audio path.")
    path = Path(asset.path)
    if not path.is_absolute():
        path = Path(project_root) / path
    path = path.resolve()
    if not validate_audio_file(path):
        raise AudioError("The listening audio is missing or empty. Your completed work is still saved; choose another item.")
    return path


_SPOKEN_MARKERS_RU = (
    "однако", "кроме того", "тем не менее",
    "таким образом", "в результате", "например", "во-первых", "во-вторых",
    "с другой стороны", "между тем", "в частности",
)


def naturalize_spoken_text(text: str, language: str = "ru") -> str:
    """Prepare authored prose for speech without changing its words or meaning.

    Edge voices react strongly to punctuation and sentence boundaries.  Generated
    passages often arrive as visually valid prose but with weak spoken phrasing.
    This conservative pass only repairs whitespace, punctuation spacing, paragraph
    boundaries, and missing commas after common Russian discourse markers.
    """

    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,;:!?])(?=[^\s\n])", r"\1 ", value)
    value = re.sub(r"(?<!\.)\.{3,}", "…", value)
    value = re.sub(r"([!?]){2,}", r"\1", value)

    if language == "ru":
        marker_pattern = "|".join(re.escape(marker) for marker in _SPOKEN_MARKERS_RU)
        value = re.sub(
            rf"(?im)(^|[.!?]\s+|\n)({marker_pattern})(?!\s*[,—-])\s+",
            lambda match: f"{match.group(1)}{match.group(2)}, ",
            value,
        )

    # A paragraph boundary gives Edge a more natural reset than one uninterrupted
    # wall of text. Preserve authored paragraphs and add one after full stops only
    # when the passage otherwise contains none and is long enough to benefit.
    if "\n" not in value and len(value) > 250:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        if len(sentences) >= 5:
            groups = [" ".join(sentences[i:i + 3]) for i in range(0, len(sentences), 3)]
            value = "\n\n".join(groups)
    return value.strip()


async def _edge_tts_save(
    text: str, voice: str, rate: str, pitch: str, volume: str, path: Path
) -> None:
    try:
        import edge_tts
    except Exception as exc:
        raise AudioError("edge-tts is not installed. Install pinned requirements or use prebuilt starter audio.") from exc
    communicator = edge_tts.Communicate(
        text=text, voice=voice, rate=rate, pitch=pitch, volume=volume
    )
    await communicator.save(str(path))


def generate_cached_tts(
    transcript: str,
    cache_dir: str | Path,
    voice: str = "ru-RU-SvetlanaNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    language: str = "ru",
    naturalize: bool = True,
    engine_version: str = "edge-tts-7",
    timeout_seconds: float = 60.0,
) -> Path:
    cache_dir = Path(cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    spoken_text = naturalize_spoken_text(transcript, language) if naturalize else transcript.strip()
    key = audio_cache_key(spoken_text, voice, rate, engine_version, pitch=pitch, volume=volume)
    output = cache_dir / f"{key}.mp3"
    if validate_audio_file(output):
        return output
    temp = output.with_suffix(".tmp.mp3")
    try:
        _get_async_runner().run(
            _edge_tts_save(spoken_text, voice, rate, pitch, volume, temp), timeout_seconds
        )
        if not validate_audio_file(temp):
            raise AudioError("TTS returned an empty or incomplete audio file.")
        os.replace(temp, output)
        return output
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def cleanup_audio_files(
    directories: Iterable[str | Path],
    max_age_seconds: int,
    referenced_paths: set[str] | None = None,
    now: float | None = None,
) -> list[Path]:
    referenced = {str(Path(path).resolve()) for path in (referenced_paths or set())}
    now = now or time.time()
    removed: list[Path] = []
    for directory in directories:
        root = Path(directory)
        if not root.exists():
            continue
        for path in root.glob("**/*"):
            if not path.is_file() or path.suffix.lower() not in {".mp3", ".wav", ".tmp"}:
                continue
            if str(path.resolve()) in referenced:
                continue
            try:
                if now - path.stat().st_mtime >= max_age_seconds:
                    path.unlink()
                    removed.append(path)
            except OSError:
                continue
    return removed


def gradio_audio_url(audio_path: str | Path) -> str:
    """Return Gradio's authenticated file route for a local audio file.

    The parent directory must also be passed to Blocks.launch(allowed_paths=...).
    Sending a compact URL instead of base64-embedding the MP3 prevents large
    callback payloads and Content-Length truncation through the Spaces proxy.
    """

    absolute = str(Path(audio_path).resolve())
    return "/gradio_api/file=" + quote(absolute, safe="/:")


def controlled_audio_html(audio_path: str, element_id: str, strict: bool) -> str:
    safe_id = "".join(ch for ch in element_id if ch.isalnum() or ch in "_-")
    source = html.escape(gradio_audio_url(audio_path), quote=True)
    completion = "Playback completed. Replay is disabled." if strict else "Playback completed. Use Play / Replay Audio to listen again."
    strict_value = "true" if strict else "false"
    return f"""
<div class="controlled-audio-wrap" aria-live="polite" data-audio-wrapper="true">
  <audio id="{safe_id}" data-controlled-audio="true" data-strict="{strict_value}" data-completion="{html.escape(completion, quote=True)}" src="{source}" controls playsinline preload="metadata"></audio>
  <div data-audio-status="true">Audio ready. Press the play button in the player.</div>
</div>
"""


def strict_audio_html(audio_path: str, element_id: str) -> str:
    return controlled_audio_html(audio_path, element_id, strict=True)
