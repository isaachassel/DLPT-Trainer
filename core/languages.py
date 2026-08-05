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
        female_voice_label="Russian Female — Svetlana",
        male_voice_label="Russian Male — Dmitry",
        starter_voice_label="Automatic natural Russian voice",
        additional_voices=(("Russian Female — Dariya", "ru-RU-DariyaNeural"),),
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

LANGUAGE_LABEL_TO_CODE = {profile.label: code for code, profile in LANGUAGES.items()}
# Preserve old UI/bookmark payloads created before high-level generated Reading
# began alternating between Simplified and Traditional characters.
LANGUAGE_LABEL_TO_CODE["Mandarin Chinese (Simplified)"] = "zh-CN"
LANGUAGE_CODE_TO_LABEL = {code: profile.label for code, profile in LANGUAGES.items()}
SUPPORTED_LANGUAGE_CODES = tuple(LANGUAGES)


def language_profile(code: str) -> LanguageProfile:
    try:
        return LANGUAGES[code]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {code}") from exc


def voice_entries(code: str) -> list[tuple[str, str]]:
    """Return stable user-facing labels and native voice IDs for a language."""

    profile = language_profile(code)
    entries = [
        (profile.female_voice_label, profile.female_voice),
        *profile.additional_voices,
        (profile.male_voice_label, profile.male_voice),
    ]
    # Keep the automatic option last for compatibility with existing saved UI
    # payloads while the layout explicitly selects it as the default value.
    entries.append((profile.starter_voice_label, profile.female_voice))
    return entries


def voice_choices(code: str) -> list[str]:
    return [label for label, _voice in voice_entries(code)]


def voice_for_label(code: str, label: str) -> str:
    entries = dict(voice_entries(code))
    profile = language_profile(code)
    return entries.get(label, profile.female_voice)




def voice_label_for_id(code: str, voice_id: str) -> str:
    """Return the user-facing label for a configured voice ID."""

    for label, configured_id in voice_entries(code):
        if configured_id == voice_id and label != language_profile(code).starter_voice_label:
            return label
    return voice_id


def voice_fallbacks(code: str, preferred_voice: str) -> tuple[str, ...]:
    """Return explicit fallback voices, preferring the same apparent gender.

    The selector must never silently map Dariya to Dmitry.  When a selected voice
    is temporarily unavailable, another same-gender native voice is tried first
    and the UI reports the substitution.
    """

    profile = language_profile(code)
    female = [profile.female_voice, *(voice for _label, voice in profile.additional_voices)]
    male = [profile.male_voice]
    if preferred_voice in female:
        ordered = [voice for voice in female if voice != preferred_voice] + male
    elif preferred_voice in male:
        ordered = [voice for voice in male if voice != preferred_voice] + female
    else:
        ordered = list(native_voice_pool(code))
    return tuple(dict.fromkeys(voice for voice in ordered if voice and voice != preferred_voice))

def native_voice_pool(code: str, preferred_voice: str | None = None) -> tuple[str, ...]:
    """Return a de-duplicated native voice pool with the preferred voice first."""

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
