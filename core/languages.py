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
        starter_voice_label="Starter-bank Russian voice",
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
        starter_voice_label="Starter-bank Mandarin voice",
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


def voice_choices(code: str) -> list[str]:
    profile = language_profile(code)
    return [profile.female_voice_label, profile.male_voice_label, profile.starter_voice_label]


def voice_for_label(code: str, label: str) -> str:
    profile = language_profile(code)
    if label == profile.male_voice_label:
        return profile.male_voice
    return profile.female_voice
