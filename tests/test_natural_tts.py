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
    assert "Однако работа" in result


def test_naturalize_spoken_text_does_not_inject_long_pause_boundaries():
    text = "Первое предложение. Второе предложение. Третье предложение. " * 5
    assert "\n" not in naturalize_spoken_text(text, "ru")


def test_natural_profile_is_stable_and_bounded():
    passage = _passage()
    profile = _natural_voice_profile(passage, Settings())
    assert profile == _natural_voice_profile(passage, Settings())
    voice, rate, pitch, volume = profile
    assert voice == "ru-RU-DmitryNeural"
    assert 1 <= int(rate.removesuffix("%")) <= 5
    assert pitch == "+0Hz"
    assert volume == "+0%"


def test_cache_key_changes_for_pitch_and_volume():
    base = audio_cache_key("текст", "voice", "+0%", "v", "+0Hz", "+0%")
    assert base != audio_cache_key("текст", "voice", "+0%", "v", "+1Hz", "+0%")

from core.audio import split_speaker_turns, _voice_for_turn


def test_split_named_russian_speaker_turns():
    script = "Ведущий: Почему изменилось решение?\nЭксперт: Появились новые данные.\nВедущий: Что будет дальше?"
    turns = split_speaker_turns(script)
    assert turns == [
        ("Ведущий", "Почему изменилось решение?"),
        ("Эксперт", "Появились новые данные."),
        ("Ведущий", "Что будет дальше?"),
    ]


def test_split_dash_dialogue_alternates_speakers():
    turns = split_speaker_turns("— Вы уже приняли решение?\n— Нет, обсуждение продолжается.\n— Когда будут итоги?")
    assert [label for label, _ in turns] == ["speaker_0", "speaker_1", "speaker_0"]


def test_single_narrator_colon_is_not_misclassified():
    assert split_speaker_turns("Главная причина: изменение погодных условий.") == []


def test_gendered_labels_receive_distinct_russian_voices():
    female = _voice_for_turn("Женщина", 0, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    male = _voice_for_turn("Мужчина", 1, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    assert female == "ru-RU-SvetlanaNeural"
    assert male == "ru-RU-DmitryNeural"


def test_naturalize_removes_pause_heavy_typography():
    result = naturalize_spoken_text("Решение…  было принято — после обсуждения.", "ru")
    assert "…" not in result
    assert " — " not in result
    assert "  " not in result
