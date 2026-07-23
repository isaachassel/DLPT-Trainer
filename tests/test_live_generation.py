from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings
from core.generation import GenerationValidationError, LiveGenerationService, MockProvider
from core.item_bank import ItemBank
from core.session import create_session
from core.validation import answer_position_balance


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        generation_provider="mock",
        max_generation_requests_per_session=3,
        generated_item_bank_path=tmp_path / "generated.jsonl",
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
        session_dir=tmp_path / "sessions",
        history_dir=tmp_path / "history",
    )


def test_live_generated_bundle_is_validated_stored_and_reloadable(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    service = LiveGenerationService(_settings(tmp_path), bank, project_root, provider=MockProvider())

    result = service.generate_and_store(
        skill="reading",
        level="2",
        mode="training",
        topics=["education"],
        competencies=["main idea", "prominent detail"],
        maximum_questions=2,
    )

    assert generated_path.exists()
    assert result.passage.id in bank.passages
    assert bank.origin_for(result.passage.id) == "generated_bank"
    assert all(question.validation_status == "accepted" for question in result.questions)
    assert all(question.answer_position_metadata.get("shuffle_map") for question in result.questions)
    assert bank.validate_operational_bank() == []
    counts = answer_position_balance(bank.questions.values())
    assert max(counts.values()) - min(counts.values()) <= 1

    reloaded = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    assert result.passage.id in reloaded.passages
    assert len(reloaded.get_questions(result.passage.id)) == 2


def test_duplicate_live_content_is_quarantined_without_polluting_bank(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    service = LiveGenerationService(_settings(tmp_path), bank, project_root, provider=MockProvider())
    service.generate_and_store(
        skill="reading", level="2", mode="training", topics=[], competencies=[], maximum_questions=2
    )
    passage_count = len(bank.passages)

    with pytest.raises(GenerationValidationError, match="duplicated"):
        service.generate_and_store(
            skill="reading", level="2", mode="training", topics=[], competencies=[], maximum_questions=2
        )

    assert len(bank.passages) == passage_count
    quarantine = tmp_path / "quarantine" / "live_generation_failures.jsonl"
    assert quarantine.exists()
    assert "duplicate" in quarantine.read_text(encoding="utf-8").lower()


def test_fresh_ai_unavailable_falls_back_without_losing_session(monkeypatch):
    import ui.callbacks as callbacks

    state = create_session(
        mode="training",
        selected_skills=["reading"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_of_passage",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
        content_source="fresh_ai_preferred",
    )
    monkeypatch.setattr(callbacks.SETTINGS, "generation_provider", "disabled")
    before_responses = list(state.responses)

    bundle = callbacks._select_with_safe_history(state)

    assert bundle.passage.id in callbacks.BANK.passages
    assert state.responses == before_responses
    assert state.bank_fallback_count == 1
    assert state.last_content_source in {"starter_bank", "generated_bank"}
    assert "fallback" in (state.last_content_note or "").lower()


def test_generation_limit_uses_reusable_bank(monkeypatch):
    import ui.callbacks as callbacks

    state = create_session(
        mode="training",
        selected_skills=["reading"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_of_passage",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
        content_source="fresh_ai_preferred",
    )
    monkeypatch.setattr(callbacks.SETTINGS, "generation_provider", "mock")
    monkeypatch.setattr(callbacks.SETTINGS, "max_generation_requests_per_session", 0)

    bundle = callbacks._select_with_safe_history(state)

    assert bundle.passage.id in callbacks.BANK.passages
    assert state.generation_requests == 0
    assert state.bank_fallback_count == 1
    assert "limit" in (state.last_content_note or "").lower()


def test_live_listening_generation_creates_validated_cached_audio(project_root, tmp_path, monkeypatch):
    import core.generation as generation

    def fake_tts(transcript, cache_dir, voice, rate, engine_version):
        path = Path(cache_dir) / "fixture.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ID3" + b"0" * 1024)
        return path

    monkeypatch.setattr(generation, "generate_cached_tts", fake_tts)
    monkeypatch.setattr(generation, "audio_duration_seconds", lambda path: 24.0)

    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    service = LiveGenerationService(_settings(tmp_path), bank, project_root, provider=MockProvider())

    result = service.generate_and_store(
        skill="listening",
        level="2",
        mode="diagnostic",
        topics=["education"],
        competencies=["main idea"],
        maximum_questions=2,
    )

    assert result.audio_asset is not None
    assert result.audio_asset.validated is True
    assert result.passage.audio_asset_id == result.audio_asset.id
    assert bank.get_audio(result.audio_asset.id) is not None
    assert Path(result.audio_asset.path).stat().st_size > 512
