from __future__ import annotations

import asyncio
import atexit
import hashlib
import html
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Coroutine, Iterable, TypeVar
from urllib.parse import quote

from .models import AudioAsset


LOGGER = logging.getLogger("dlpt.audio")

DIALOGUE_TTS_CACHE_VERSION = "edge-tts-7.2.8-dialogue-v5-three-native-voices"
DIALOGUE_TTS_ASSET_VERSION = "7.2.8-dialogue-v5-three-native-voices"


class AudioError(RuntimeError):
    pass


class VoiceUnavailableError(AudioError):
    """A requested Edge voice failed before a valid segment was produced."""

    def __init__(self, voice: str, reason: str = "voice synthesis failed") -> None:
        self.voice = voice
        super().__init__(f"Voice {voice} was unavailable: {reason}")


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


def naturalize_spoken_text(text: str, language: str = "ru") -> str:
    """Prepare authored text for fluent TTS without changing its words.

    Edge can turn typography intended for reading—nonbreaking spaces, spaced
    dashes, ellipses, and repeated punctuation—into conspicuous silence. The
    display transcript remains untouched; only the synthesis copy is normalized.
    """

    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n+ *", " ", value)
    value = re.sub(r"\.{3,}|…+", ", ", value)
    value = re.sub(r"\s+[—–-]\s+", ", ", value)
    value = re.sub(r"([!?.,;:])\1+", r"\1", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,;:!?])(?=[^\s])", r"\1 ", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


_SPEAKER_LINE = re.compile(
    r"^\s*(?P<label>[А-ЯЁA-Z][А-Яа-яЁёA-Za-z0-9 ._-]{0,30})\s*[:：]\s*(?P<text>.+?)\s*$"
)
_KNOWN_SPEAKER_LABELS = {
    "ведущий", "ведущая", "журналист", "журналистка", "корреспондент",
    "корреспондентка", "интервьюер", "интервьюируемый", "респондент",
    "гость", "гост", "гостья", "эксперт", "экспертка", "мужчина", "женщина",
    "диктор", "дикторша", "сотрудник", "сотрудница", "репортёр", "репортер",
    "клиент", "клиентка", "врач", "пациент", "пациентка", "учитель",
    "учительница", "студент", "студентка", "speaker 1", "speaker 2",
    "host", "guest", "interviewer", "reporter", "expert", "man", "woman",
    "主持人", "记者", "嘉宾", "专家", "男", "女", "顾客", "工作人员",
}


def _speaker_marker_pattern() -> re.Pattern[str]:
    labels = sorted(_KNOWN_SPEAKER_LABELS, key=len, reverse=True)
    alternatives = "|".join(re.escape(label) for label in labels)
    generic = r"(?:speaker|говорящий|собеседник)\s*[12абab]"
    return re.compile(
        rf"(?<![\wА-Яа-яЁё])(?P<label>{alternatives}|{generic})\s*[:：]\s*",
        re.IGNORECASE,
    )


_SPEAKER_MARKER = _speaker_marker_pattern()


def strip_speaker_labels(text: str) -> str:
    """Remove role labels from the synthesis copy under all circumstances."""

    value = str(text or "")
    value = _SPEAKER_MARKER.sub("", value)
    return re.sub(r"(?m)^\s*[—–-]\s*", "", value).strip()


def split_speaker_turns(text: str) -> list[tuple[str, str]]:
    """Extract dialogue turns while keeping all labels out of spoken text."""

    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_SPEAKER_MARKER.finditer(raw))
    labelled: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        turn = raw[start:stop].strip(" \t\n—–-")
        turn = strip_speaker_labels(turn)
        if turn:
            labelled.append((match.group("label").strip(), turn))
    if len(labelled) >= 2 and len({label.casefold() for label, _ in labelled}) >= 2:
        return labelled

    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    dashed: list[str] = []
    for line in lines:
        match = re.match(r"^[—–-]\s*(.+?)\s*$", line)
        if match:
            cleaned = strip_speaker_labels(match.group(1).strip())
            if cleaned:
                dashed.append(cleaned)
    if len(dashed) >= 2:
        return [(f"speaker_{index % 2}", turn) for index, turn in enumerate(dashed)]
    return []
_FEMALE_LABEL_CUES = (
    "женщина", "ведущая", "журналистка", "корреспондентка", "гостья",
    "экспертка", "сотрудница", "клиентка", "пациентка", "учительница",
    "студентка", "woman", "female", "女",
)
# Only explicit male cues are treated as hard gender information. Generic Russian
# role nouns such as ``ведущий``, ``гость``, and ``эксперт`` are deliberately not
# hard-coded to Dmitry.
_MALE_LABEL_CUES = ("мужчина", "man", "male", "男")

_RUSSIAN_NATIVE_VOICES = (
    "ru-RU-DmitryNeural",
    "ru-RU-SvetlanaNeural",
    "ru-RU-DariyaNeural",
)
_MANDARIN_NATIVE_VOICES = (
    "zh-CN-YunxiNeural",
    "zh-CN-XiaoxiaoNeural",
)


@dataclass(frozen=True)
class SpeakerVoiceProfile:
    voice: str
    rate: str


def _speaker_gender_preference(label: str) -> str | None:
    normalized = label.casefold().strip()
    if any(cue in normalized for cue in _FEMALE_LABEL_CUES):
        return "female"
    if any(cue in normalized for cue in _MALE_LABEL_CUES):
        return "male"
    return None


def _voice_gender(voice: str) -> str | None:
    if any(name in voice for name in ("Svetlana", "Dariya", "Xiaoxiao")):
        return "female"
    if any(name in voice for name in ("Dmitry", "Yunxi")):
        return "male"
    return None


def _native_voice_pool(language: str, primary_voice: str) -> list[str]:
    configured = _MANDARIN_NATIVE_VOICES if language == "zh-CN" else _RUSSIAN_NATIVE_VOICES
    ordered = [primary_voice, *configured]
    pool: list[str] = []
    for candidate in ordered:
        if candidate and candidate not in pool:
            pool.append(candidate)
    return pool


def _parse_rate_percent(rate: str) -> int:
    match = re.fullmatch(r"([+-]?)(\d+)%", str(rate).strip())
    if not match:
        return 0
    value = int(match.group(2))
    return -value if match.group(1) == "-" else value


def _rate_with_delta(rate: str, delta: int) -> str:
    value = max(-35, min(35, _parse_rate_percent(rate) + delta))
    return f"{value:+d}%"


def _dialogue_speaker_profiles(
    turns: list[tuple[str, str]],
    primary_voice: str,
    language: str,
    base_rate: str = "+0%",
    voice_pool: Iterable[str] | None = None,
) -> dict[str, SpeakerVoiceProfile]:
    """Assign stable voices to speaker identities.

    Russian gets three distinct native neural voices: Dmitry, Svetlana, and
    Dariya. A fourth distinct speaker reuses a native voice with a restrained
    rate difference so the role remains distinguishable without artificial pitch
    manipulation. Repeated turns always retain the same profile.
    """

    unique_labels: list[str] = []
    original_labels: dict[str, str] = {}
    for label, _text in turns:
        key = label.casefold().strip()
        if key and key not in original_labels:
            original_labels[key] = label
            unique_labels.append(key)
    if not unique_labels:
        return {}

    pool = []
    for candidate in (list(voice_pool) if voice_pool is not None else _native_voice_pool(language, primary_voice)):
        if candidate and candidate not in pool:
            pool.append(candidate)
    if not pool:
        pool = [primary_voice]

    mapping: dict[str, SpeakerVoiceProfile] = {}
    unused = list(pool)
    voice_use_count: dict[str, int] = {voice: 0 for voice in pool}

    for index, key in enumerate(unique_labels):
        preference = _speaker_gender_preference(original_labels[key])
        chosen: str | None = None

        # The user's selected/default primary voice owns the first generic role.
        if index == 0 and primary_voice in unused and (
            preference is None or _voice_gender(primary_voice) == preference
        ):
            chosen = primary_voice

        if chosen is None and preference is not None:
            chosen = next((voice for voice in unused if _voice_gender(voice) == preference), None)
        if chosen is None and unused:
            chosen = unused[0]
        if chosen is None:
            matching = [voice for voice in pool if preference is None or _voice_gender(voice) == preference]
            candidates = matching or pool
            chosen = candidates[index % len(candidates)]

        if chosen in unused:
            unused.remove(chosen)

        reuse_index = voice_use_count.get(chosen, 0)
        voice_use_count[chosen] = reuse_index + 1
        # First use keeps the requested rate. Reused voices receive small,
        # bounded timing differences; pitch remains untouched.
        reuse_deltas = (0, -4, +4, -7, +7)
        delta = reuse_deltas[min(reuse_index, len(reuse_deltas) - 1)]
        mapping[key] = SpeakerVoiceProfile(chosen, _rate_with_delta(base_rate, delta))

    return mapping


def _dialogue_voice_map(
    turns: list[tuple[str, str]], primary_voice: str, secondary_voice: str
) -> dict[str, str]:
    """Backward-compatible voice-only map used by tests and extensions."""

    language = "zh-CN" if primary_voice.startswith("zh-") else "ru"
    pool = [primary_voice, secondary_voice, *_native_voice_pool(language, primary_voice)]
    profiles = _dialogue_speaker_profiles(
        turns, primary_voice, language, voice_pool=pool
    )
    return {key: profile.voice for key, profile in profiles.items()}


def _voice_for_turn(label: str, index: int, primary_voice: str, secondary_voice: str) -> str:
    """Compatibility helper for isolated turn tests."""

    preference = _speaker_gender_preference(label)
    if preference is not None:
        for candidate in (primary_voice, secondary_voice):
            if _voice_gender(candidate) == preference:
                return candidate
    return primary_voice if index % 2 == 0 else secondary_voice


def _opposite_voice(language: str, voice: str) -> str:
    pool = _native_voice_pool(language, voice)
    return next((candidate for candidate in pool if candidate != voice), voice)


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


def generate_dialogue_cached_tts(
    transcript: str,
    cache_dir: str | Path,
    voice: str = "ru-RU-SvetlanaNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    language: str = "ru",
    engine_version: str = DIALOGUE_TTS_CACHE_VERSION,
    timeout_seconds: float = 60.0,
    synthesizer=None,
    voice_pool: Iterable[str] | None = None,
    allow_segment_fallback: bool = True,
) -> Path:
    """Generate one narrator or a real multi-speaker recording.

    Only detected dialogue is segmented. Each distinct Russian speaker receives
    an unused native voice first (Dmitry, Svetlana, Dariya). Speaker labels never
    reach TTS. Four-plus speaker scripts reuse voices with restrained rate
    differences rather than fake pitch shifts.
    """

    synth = synthesizer or generate_cached_tts
    turns = split_speaker_turns(transcript)
    if not turns:
        try:
            return synth(
                strip_speaker_labels(transcript), cache_dir, voice=voice, rate=rate, pitch=pitch, volume=volume,
                language=language, naturalize=True, engine_version=engine_version,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            if not allow_segment_fallback:
                raise VoiceUnavailableError(voice, type(exc).__name__) from exc
            raise

    profiles = _dialogue_speaker_profiles(
        turns, voice, language, base_rate=rate, voice_pool=voice_pool
    )
    plan = [
        (
            label,
            naturalize_spoken_text(turn, language),
            profiles[label.casefold().strip()].voice,
            profiles[label.casefold().strip()].rate,
        )
        for label, turn in turns if turn.strip()
    ]
    LOGGER.info(
        "Dialogue TTS plan speakers=%s profiles=%s turns=%s",
        list(dict.fromkeys(label for label, _spoken, _voice, _rate in plan)),
        list(dict.fromkeys(f"{speaker_voice}@{speaker_rate}" for _label, _spoken, speaker_voice, speaker_rate in plan)),
        len(plan),
    )
    if len(plan) < 2:
        try:
            return synth(
                strip_speaker_labels(transcript), cache_dir, voice=voice, rate=rate, pitch=pitch, volume=volume,
                language=language, naturalize=True, engine_version=engine_version,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            if not allow_segment_fallback:
                raise VoiceUnavailableError(voice, type(exc).__name__) from exc
            raise

    cache_root = Path(cache_dir).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    signature = "\n".join(
        f"{label}|{speaker_voice}|{speaker_rate}|{spoken}"
        for label, spoken, speaker_voice, speaker_rate in plan
    )
    voice_signature = "+".join(dict.fromkeys(speaker_voice for _label, _spoken, speaker_voice, _rate in plan))
    key = audio_cache_key(signature, voice_signature, rate, engine_version, pitch, volume)
    output = cache_root / f"{key}.mp3"
    if validate_audio_file(output):
        return output

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError("Multi-speaker audio requires ffmpeg, which is missing from this runtime.")

    temp_output = output.with_suffix(".tmp.mp3")
    with tempfile.TemporaryDirectory(prefix="dlpt_dialogue_", dir=cache_root) as work_dir:
        work = Path(work_dir)
        segment_paths: list[Path] = []
        for index, (_label, spoken, speaker_voice, speaker_rate) in enumerate(plan):
            try:
                segment = synth(
                    spoken, work, voice=speaker_voice, rate=speaker_rate, pitch=pitch, volume=volume,
                    language=language, naturalize=False, engine_version=f"{engine_version}-segment",
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                if not allow_segment_fallback:
                    raise VoiceUnavailableError(speaker_voice, type(exc).__name__) from exc
                # The live service can change independently. Canonical/automatic
                # recordings may degrade gracefully, while explicit Training
                # selections disable this silent segment-level substitution.
                fallback_candidates = list(voice_pool) if voice_pool is not None else _native_voice_pool(language, voice)
                fallback_pool = [candidate for candidate in fallback_candidates if candidate != speaker_voice]
                if not fallback_pool:
                    raise
                fallback_voice = fallback_pool[index % len(fallback_pool)]
                fallback_rate = _rate_with_delta(speaker_rate, -4 if index % 2 == 0 else +4)
                LOGGER.warning(
                    "Dialogue voice unavailable voice=%s; retrying voice=%s rate=%s reason=%s",
                    speaker_voice, fallback_voice, fallback_rate, type(exc).__name__,
                )
                segment = synth(
                    spoken, work, voice=fallback_voice, rate=fallback_rate, pitch=pitch, volume=volume,
                    language=language, naturalize=False, engine_version=f"{engine_version}-segment-fallback",
                    timeout_seconds=timeout_seconds,
                )
            segment_paths.append(segment)

        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        for segment in segment_paths:
            command.extend(["-i", str(segment)])
        labels = [f"[{index}:a]" for index in range(len(segment_paths))]
        filters = ["".join(labels) + f"concat=n={len(segment_paths)}:v=0:a=1[outa]"]
        command.extend([
            "-filter_complex", ";".join(filters), "-map", "[outa]",
            "-codec:a", "libmp3lame", "-q:a", "3", str(temp_output),
        ])
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=max(30, int(timeout_seconds)))
        except subprocess.CalledProcessError as exc:
            raise AudioError(f"Multi-speaker audio assembly failed: {exc.stderr[-240:]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioError("Multi-speaker audio assembly timed out.") from exc

    if not validate_audio_file(temp_output):
        temp_output.unlink(missing_ok=True)
        raise AudioError("Multi-speaker audio assembly returned an empty or incomplete file.")
    os.replace(temp_output, output)
    return output


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
