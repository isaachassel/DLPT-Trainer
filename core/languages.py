from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    label: str
    short_label: str
    source_name: str
    native_name: str
    female_voice: str
    male_voice: str
    female_voice_label: str
    male_voice_label: str
    starter_voice_label: str
    additional_voices: tuple[tuple[str, str], ...] = ()


LANGUAGES: dict[str, LanguageProfile] = {
    "ru": LanguageProfile(
        code="ru",
        label="Russian",
        short_label="Russian",
        source_name="Russian",
        native_name="Русский",
        female_voice="ru-RU-SvetlanaNeural",
        male_voice="ru-RU-DmitryNeural",
        female_voice_label="Russian Female — Svetlana (Edge)",
        male_voice_label="Russian Male — Dmitry (Edge)",
        starter_voice_label="Automatic natural Russian voice",
        additional_voices=(
            ("Russian Female — Irina (local Piper)", "piper:ru_RU-irina-medium"),
            ("Russian Male — Ruslan (local Piper)", "piper:ru_RU-ruslan-medium"),
        ),
    ),
    "zh-CN": LanguageProfile(
        code="zh-CN",
        label="Mandarin Chinese",
        short_label="Mandarin",
        source_name="Mandarin Chinese",
        native_name="普通话（简体/繁體中文）",
        female_voice="zh-CN-XiaoxiaoNeural",
        male_voice="zh-CN-YunxiNeural",
        female_voice_label="Mandarin Female — Xiaoxiao",
        male_voice_label="Mandarin Male — Yunxi",
        starter_voice_label="Automatic natural Mandarin voice",
    ),
}

LEGACY_VOICE_LABEL_ALIASES: dict[tuple[str, str], str] = {
    ("ru", "Russian Female — Svetlana"): "Russian Female — Svetlana (Edge)",
    ("ru", "Russian Male — Dmitry"): "Russian Male — Dmitry (Edge)",
    # Dariya is not exposed by the free Edge endpoint used by edge-tts. Existing
    # saved sessions migrate to the supplemental local female voice instead of
    # silently pretending Dariya was rendered.
    ("ru", "Russian Female — Dariya"): "Russian Female — Irina (local Piper)",
}

LANGUAGE_LABEL_TO_CODE = {profile.label: code for code, profile in LANGUAGES.items()}
LANGUAGE_LABEL_TO_CODE["Mandarin Chinese (Simplified)"] = "zh-CN"
LANGUAGE_CODE_TO_LABEL = {code: profile.label for code, profile in LANGUAGES.items()}
SUPPORTED_LANGUAGE_CODES = tuple(LANGUAGES)


def language_profile(code: str) -> LanguageProfile:
    try:
        return LANGUAGES[code]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {code}") from exc


def voice_entries(code: str) -> list[tuple[str, str]]:
    profile = language_profile(code)
    entries = [
        (profile.female_voice_label, profile.female_voice),
        *profile.additional_voices,
        (profile.male_voice_label, profile.male_voice),
    ]
    entries.append((profile.starter_voice_label, profile.female_voice))
    return entries


def voice_choices(code: str) -> list[str]:
    return [label for label, _voice in voice_entries(code)]


def normalize_voice_label(code: str, label: str) -> str:
    return LEGACY_VOICE_LABEL_ALIASES.get((code, label), label)


def voice_for_label(code: str, label: str) -> str:
    label = normalize_voice_label(code, label)
    entries = dict(voice_entries(code))
    profile = language_profile(code)
    return entries.get(label, profile.female_voice)


def voice_label_for_id(code: str, voice_id: str) -> str:
    for label, configured_id in voice_entries(code):
        if configured_id == voice_id and label != language_profile(code).starter_voice_label:
            return label
    return voice_id


def voice_gender(voice_id: str) -> str | None:
    lower = voice_id.casefold()
    if any(token in lower for token in ("svetlana", "irina", "xiaoxiao")):
        return "female"
    if any(token in lower for token in ("dmitry", "ruslan", "yunxi")):
        return "male"
    return None


def native_voice_pool(code: str, preferred_voice: str | None = None) -> tuple[str, ...]:
    profile = language_profile(code)
    configured = [
        profile.male_voice,
        profile.female_voice,
        *(voice for _label, voice in profile.additional_voices),
    ]
    ordered = ([preferred_voice] if preferred_voice else []) + configured
    result: list[str] = []
    for voice in ordered:
        if voice and voice not in result:
            result.append(voice)
    return tuple(result)


def voice_fallbacks(code: str, preferred_voice: str) -> tuple[str, ...]:
    preferred_gender = voice_gender(preferred_voice)
    pool = list(native_voice_pool(code))
    same_gender = [voice for voice in pool if voice != preferred_voice and voice_gender(voice) == preferred_gender]
    other = [voice for voice in pool if voice != preferred_voice and voice not in same_gender]
    return tuple(same_gender + other)
