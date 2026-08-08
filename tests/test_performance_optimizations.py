from __future__ import annotations

from types import SimpleNamespace

from core.item_bank import ItemBank
from core.session import create_session
from ui.callbacks import (
    _asset_is_current_for_passage,
    _canonical_audio_matches,
    _fresh_generation_audio_preferences,
)


def _session(*, voice_label: str, speed: str = "Normal"):
    return create_session(
        language="ru",
        mode="training",
        selected_skills=["listening"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label=voice_label,
        speech_rate_label=speed,
    )


def test_active_passage_validation_is_cached(monkeypatch, project_root):
    import core.item_bank as item_bank_module

    bank = ItemBank(
        [
            project_root / "data/starter_items.jsonl",
            project_root / "data/mandarin_starter_items.jsonl",
        ],
        writable_path=project_root / "storage/item_bank/generated_items.jsonl",
    ).load()
    passage_calls = 0
    question_calls = 0
    real_passage = item_bank_module.validate_passage
    real_question = item_bank_module.validate_question

    def counted_passage(*args, **kwargs):
        nonlocal passage_calls
        passage_calls += 1
        return real_passage(*args, **kwargs)

    def counted_question(*args, **kwargs):
        nonlocal question_calls
        question_calls += 1
        return real_question(*args, **kwargs)

    monkeypatch.setattr(item_bank_module, "validate_passage", counted_passage)
    monkeypatch.setattr(item_bank_module, "validate_question", counted_question)

    first = bank.active_passages("reading", "ru")
    first_counts = (passage_calls, question_calls)
    second = bank.active_passages("reading", "ru")

    assert first
    assert [item.id for item in second] == [item.id for item in first]
    assert first_counts[0] > 0
    assert first_counts[1] > 0
    assert (passage_calls, question_calls) == first_counts


def test_health_summary_cache_returns_an_independent_copy(project_root):
    bank = ItemBank(
        [
            project_root / "data/starter_items.jsonl",
            project_root / "data/mandarin_starter_items.jsonl",
        ],
        writable_path=project_root / "storage/item_bank/generated_items.jsonl",
    ).load()

    first = bank.health_summary("ru")
    first["reading"]["passages"] = -1
    second = bank.health_summary("ru")

    assert second["reading"]["passages"] >= 0


def test_explicit_training_voice_is_forwarded_to_first_fresh_audio_render():
    state = _session(voice_label="Russian Female — Irina (local Piper)", speed="Fast")

    assert _fresh_generation_audio_preferences(state) == {
        "preferred_audio_voice": "piper:ru_RU-irina-medium",
        "preferred_audio_rate": "+10%",
        "preferred_audio_pitch": "+0Hz",
        "preferred_audio_volume": "+0%",
    }


def test_automatic_training_voice_keeps_passage_aware_profile_selection():
    state = _session(voice_label="Automatic natural Russian voice")
    assert _fresh_generation_audio_preferences(state) == {}


def test_current_canonical_audio_can_be_reused_without_second_tts_render():
    asset = SimpleNamespace(
        engine_version="hybrid-edge-piper-dialogue-v6",
        voice="ru-RU-DmitryNeural",
        rate="+10%",
    )
    assert _canonical_audio_matches(asset, "ru-RU-DmitryNeural", "+10%") is True
    assert _canonical_audio_matches(asset, "ru-RU-SvetlanaNeural", "+10%") is False
    assert _canonical_audio_matches(asset, "ru-RU-DmitryNeural", "+0%") is False


def test_old_dialogue_asset_is_regenerated_after_role_parser_upgrade():
    asset = SimpleNamespace(
        engine_version="hybrid-edge-piper-dialogue-v6",
        voice="ru-RU-DmitryNeural",
        rate="+5%",
        validated=True,
    )
    passage = SimpleNamespace(
        passage_ru="Продавец: Добрый день.\nПокупатель: Мне нужен билет.\nПродавец: Конечно."
    )
    assert _asset_is_current_for_passage(asset, passage) is False

    current = SimpleNamespace(
        engine_version="hybrid-edge-piper-dialogue-v8",
        voice="ru-RU-DmitryNeural",
        rate="+5%",
        validated=True,
    )
    assert _asset_is_current_for_passage(current, passage) is True


def test_production_dialogue_segments_are_rendered_with_bounded_parallelism(monkeypatch, tmp_path):
    import shutil
    import subprocess
    import threading
    import time
    import core.audio as audio

    if not shutil.which("ffmpeg"):
        import pytest
        pytest.skip("ffmpeg is required")

    state = {"active": 0, "maximum": 0, "counter": 0}
    lock = threading.Lock()

    def fake_cached_tts(text, cache_dir, **kwargs):
        with lock:
            state["active"] += 1
            state["maximum"] = max(state["maximum"], state["active"])
            state["counter"] += 1
            index = state["counter"]
        try:
            time.sleep(0.15)
            output = tmp_path / f"parallel-segment-{index}.mp3"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"sine=frequency={400 + index * 50}:duration=0.15",
                    "-codec:a", "libmp3lame", "-q:a", "4", str(output),
                ],
                check=True,
            )
            return output
        finally:
            with lock:
                state["active"] -= 1

    monkeypatch.setattr(audio, "generate_cached_tts", fake_cached_tts)
    output = audio.generate_dialogue_cached_tts(
        "Ведущий: Один.\nГость: Два.\nЭксперт: Три.",
        tmp_path,
        engine_version="parallel-regression-v1",
    )

    assert output.exists()
    assert state["maximum"] >= 2
    assert state["maximum"] <= 3


def test_prior_stable_v170_neural_audio_is_reused_without_regeneration():
    asset = SimpleNamespace(
        engine="hybrid-edge-piper",
        engine_version="hybrid-edge-piper-dialogue-v5",
        voice="ru-RU-DmitryNeural",
        rate="+5%",
        validated=True,
    )
    assert _canonical_audio_matches(asset, "ru-RU-DmitryNeural", "+5%") is True
