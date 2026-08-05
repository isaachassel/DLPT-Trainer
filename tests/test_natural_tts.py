from pathlib import Path

from core.audio import audio_cache_key, naturalize_spoken_text
from core.config import Settings
from core.generation import _natural_voice_profile
from core.models import GenerationMetadata, PassageItem


def _passage(genre: str = "news report", language: str = "ru") -> PassageItem:
    text = "По данным министерства ситуация изменилась. Однако власти продолжают работу. " * 4
    return PassageItem(
        id="p1", language=language, skill="listening", target_ilr="2",
        provisional_difficulty=0.5, genre=genre, topic="government", subtopic="public update",
        orientation_en="You will hear a report.", passage_ru=text, word_count=len(text.split()),
        question_ids=["q1"], content_hash="abc123", duplicate_detection_hash="abc123",
        generation=GenerationMetadata(),
    )


def test_naturalize_spoken_text_repairs_russian_discourse_pauses():
    result = naturalize_spoken_text("По данным министерства всё готово. Однако работа продолжается.", "ru")
    assert "По данным, министерства" not in result
    assert "По данным министерства" in result
    assert "Однако, работа" in result


def test_naturalize_spoken_text_adds_paragraph_resets_to_long_flat_prose():
    text = "Первое предложение. Второе предложение. Третье предложение. " * 5
    assert "\n\n" in naturalize_spoken_text(text, "ru")


def test_natural_profile_is_stable_and_bounded():
    passage = _passage()
    profile = _natural_voice_profile(passage, Settings())
    assert profile == _natural_voice_profile(passage, Settings())
    voice, rate, pitch, volume = profile
    assert voice == "ru-RU-DmitryNeural"
    assert -3 <= int(rate.removesuffix("%")) <= 3
    assert -3 <= int(pitch.removesuffix("Hz")) <= 3
    assert volume == "+0%"


def test_cache_key_changes_for_pitch_and_volume():
    base = audio_cache_key("текст", "voice", "+0%", "v", "+0Hz", "+0%")
    assert base != audio_cache_key("текст", "voice", "+0%", "v", "+1Hz", "+0%")
