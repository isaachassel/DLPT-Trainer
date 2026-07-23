from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterable

from .models import AudioAsset


class AudioError(RuntimeError):
    pass


def audio_cache_key(transcript: str, voice: str, rate: str, engine_version: str) -> str:
    raw = "\n".join([transcript.strip(), voice.strip(), rate.strip(), engine_version.strip()])
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
            capture_output=True, text=True, check=True, timeout=10,
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
    if not validate_audio_file(path):
        raise AudioError("The listening audio is missing or empty. Your completed work is still saved; choose another item.")
    return path


async def _edge_tts_save(text: str, voice: str, rate: str, path: Path) -> None:
    try:
        import edge_tts
    except Exception as exc:
        raise AudioError("edge-tts is not installed. Install pinned requirements or use prebuilt starter audio.") from exc
    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicator.save(str(path))


def generate_cached_tts(
    transcript: str,
    cache_dir: str | Path,
    voice: str = "ru-RU-SvetlanaNeural",
    rate: str = "+0%",
    engine_version: str = "edge-tts-7",
) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = audio_cache_key(transcript, voice, rate, engine_version)
    output = cache_dir / f"{key}.mp3"
    if validate_audio_file(output):
        return output
    temp = output.with_suffix(".tmp.mp3")
    try:
        asyncio.run(_edge_tts_save(transcript, voice, rate, temp))
        if not validate_audio_file(temp):
            raise AudioError("TTS returned an empty or incomplete audio file.")
        os.replace(temp, output)
        return output
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_edge_tts_save(transcript, voice, rate, temp))
        finally:
            loop.close()
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


def controlled_audio_html(audio_path: str, element_id: str, strict: bool) -> str:
    safe_id = "".join(ch for ch in element_id if ch.isalnum() or ch in "_-")
    encoded = base64.b64encode(Path(audio_path).read_bytes()).decode("ascii")
    source = f"data:audio/mpeg;base64,{encoded}"
    completion = "Playback completed. Replay is disabled." if strict else "Playback completed. Use Play / Replay Audio to listen again."
    return f"""
<div class="controlled-audio-wrap" aria-live="polite">
  <audio id="{safe_id}" src="{source}" autoplay preload="auto"></audio>
  <div id="{safe_id}_status">Playing audio…</div>
</div>
<script>
(() => {{{{
  const audio = document.getElementById('{safe_id}');
  const status = document.getElementById('{safe_id}_status');
  if (!audio) return;
  audio.controls = false;
  audio.addEventListener('ended', () => {{{{ status.textContent = '{completion}'; audio.removeAttribute('src'); audio.load(); }}}});
  audio.addEventListener('error', () => {{{{ status.textContent = 'Audio could not play. Completed work remains saved.'; }}}});
}}}})();
</script>
"""


def strict_audio_html(audio_path: str, element_id: str) -> str:
    return controlled_audio_html(audio_path, element_id, strict=True)
