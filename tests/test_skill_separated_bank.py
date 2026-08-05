from __future__ import annotations

from pathlib import Path

import pytest

from core.item_bank import ItemBank, ItemBankError
from core.models import AudioAsset
from core.validation import content_hash, validate_passage, validate_question
from ui.callbacks import BANK, TOPICS_BY_SKILL, topic_controls


def _overlay_bank(project_root: Path, tmp_path: Path) -> ItemBank:
    overlay = tmp_path / "generated_items.jsonl"
    return ItemBank(
        [project_root / "data/starter_items.jsonl", overlay],
        writable_path=overlay,
    ).load()


def test_bank_maintains_separate_skill_indexes(bank):
    assert bank.passage_ids_by_skill["reading"]
    assert bank.passage_ids_by_skill["listening"]
    assert bank.passage_ids_by_skill["reading"].isdisjoint(bank.passage_ids_by_skill["listening"])
    assert all(bank.passages[pid].skill == "reading" for pid in bank.passage_ids_by_skill["reading"])
    assert all(bank.passages[pid].skill == "listening" for pid in bank.passage_ids_by_skill["listening"])


def test_skill_audio_contract_is_operational(bank):
    assert all(p.audio_asset_id is None for p in bank.active_passages("reading"))
    assert all(p.audio_duration_seconds is None for p in bank.active_passages("reading"))
    assert all(not p.voice_metadata for p in bank.active_passages("reading"))
    assert all(p.audio_asset_id in bank.audio_assets for p in bank.active_passages("listening"))
    assert all(bank.audio_assets[p.audio_asset_id].validated for p in bank.active_passages("listening"))


def test_health_summary_separates_reading_and_listening(bank):
    health = bank.health_summary()
    assert health["reading"]["passages"] + health["listening"]["passages"] == health["passages"]
    assert health["reading"]["questions"] + health["listening"]["questions"] == health["questions"]
    assert health["listening"]["audio_assets"] == health["audio_assets"]
    assert health["listening"]["missing_or_invalid_audio"] == 0


def test_topic_choices_follow_selected_skill():
    reading = topic_controls("Reading", [])
    listening = topic_controls("Listening", [])
    combined = topic_controls("Reading + Listening (separate sections)", [])
    from core.topics import CANONICAL_TOPICS
    expected = set(CANONICAL_TOPICS)
    assert set(reading["choices"]) == expected
    assert set(listening["choices"]) == expected
    assert set(combined["choices"]) == expected
    assert not any("bike" in choice.casefold() for choice in reading["choices"])


def test_reading_bundle_with_audio_is_rejected(project_root, tmp_path):
    bank = _overlay_bank(project_root, tmp_path)
    source = bank.get_passage("r005")
    source_q = bank.get_questions(source.id)[0]
    audio = next(iter(bank.audio_assets.values()))
    passage_id = "generated_reading_with_audio"
    question = source_q.model_copy(update={"id": f"{passage_id}_q1", "passage_id": passage_id})
    passage = source.model_copy(update={
        "id": passage_id,
        "question_ids": [question.id],
        "audio_asset_id": audio.id,
        "audio_duration_seconds": audio.duration_seconds,
        "voice_metadata": {"voice": "invalid-for-reading"},
        "passage_ru": source.passage_ru + " Дополнение.",
        "word_count": source.word_count + 1,
        "content_hash": content_hash(source.passage_ru + " Дополнение."),
        "duplicate_detection_hash": content_hash(source.passage_ru + " Дополнение."),
    })
    question = question.model_copy(update={"evidence_ru": question.evidence_ru})
    with pytest.raises(ItemBankError, match="reading passage"):
        bank.append_validated_bundle(
            passage,
            [question],
            validate_passage(passage, [question]),
            [validate_question(question, passage)],
            audio,
        )


def test_listening_bundle_without_audio_is_rejected(project_root, tmp_path):
    bank = _overlay_bank(project_root, tmp_path)
    source = bank.get_passage("l001")
    source_questions = bank.get_questions(source.id)
    passage_id = "generated_listening_without_audio"
    questions = [q.model_copy(update={"id": f"{passage_id}_q{i+1}", "passage_id": passage_id}) for i, q in enumerate(source_questions)]
    passage = source.model_copy(update={
        "id": passage_id,
        "question_ids": [q.id for q in questions],
        "audio_asset_id": None,
        "audio_duration_seconds": None,
        "voice_metadata": {},
        "passage_ru": source.passage_ru + " Дополнение.",
        "word_count": source.word_count + 1,
        "content_hash": content_hash(source.passage_ru + " Дополнение."),
        "duplicate_detection_hash": content_hash(source.passage_ru + " Дополнение."),
    })
    with pytest.raises(ItemBankError, match="missing audio_asset_id"):
        bank.append_validated_bundle(
            passage,
            questions,
            validate_passage(passage, questions),
            [validate_question(q, passage) for q in questions],
            None,
        )


def test_cross_skill_duplicate_is_stored_as_related_not_same_skill_duplicate(project_root, tmp_path):
    bank = _overlay_bank(project_root, tmp_path)
    listening = bank.get_passage("l001")
    source_questions = bank.get_questions(listening.id)
    passage_id = "reading_transform_of_l001"
    questions = [q.model_copy(update={"id": f"{passage_id}_q{i+1}", "passage_id": passage_id}) for i, q in enumerate(source_questions)]
    reading = listening.model_copy(update={
        "id": passage_id,
        "skill": "reading",
        "question_ids": [q.id for q in questions],
        "audio_asset_id": None,
        "audio_duration_seconds": None,
        "voice_metadata": {},
        "provenance": {"authoring_method": "test transform"},
    })
    bank.append_validated_bundle(
        reading,
        questions,
        validate_passage(reading, questions),
        [validate_question(q, reading) for q in questions],
        None,
    )
    stored = bank.get_passage(passage_id)
    assert stored.provenance["cross_skill_related_passage_id"] == listening.id
    assert bank.duplicate_of(stored, same_skill_only=True) == stored.id
    assert bank.cross_skill_duplicate_of(stored) == listening.id


def test_cross_skill_seen_content_is_filtered_before_selection(project_root, tmp_path, monkeypatch):
    from core.models import AbilityEstimate, AdaptiveSelection

    bank = _overlay_bank(project_root, tmp_path)
    listening = bank.get_passage("l001")
    source_questions = bank.get_questions(listening.id)
    passage_id = "reading_transform_for_exposure_test"
    questions = [q.model_copy(update={"id": f"{passage_id}_q{i+1}", "passage_id": passage_id}) for i, q in enumerate(source_questions)]
    reading = listening.model_copy(update={
        "id": passage_id,
        "skill": "reading",
        "question_ids": [q.id for q in questions],
        "audio_asset_id": None,
        "audio_duration_seconds": None,
        "voice_metadata": {},
        "provenance": {"authoring_method": "test transform"},
    })
    bank.append_validated_bundle(
        reading,
        questions,
        validate_passage(reading, questions),
        [validate_question(q, reading) for q in questions],
        None,
    )

    captured: list[str] = []

    def fake_selector(passages, *_args, **_kwargs):
        captured.extend(p.id for p in passages)
        chosen = next(p for p in passages if p.id != passage_id)
        return AdaptiveSelection(
            passage_id=chosen.id,
            skill="reading",
            score=1.0,
            information=1.0,
            ability_distance=0.0,
        )

    monkeypatch.setattr("core.item_bank.select_passage", fake_selector)
    bank.select(
        skill="reading",
        estimate=AbilityEstimate(skill="reading"),
        mode="training",
        target_level="1+",
        seen_passages={listening.id},
        seen_questions=set(),
        topic_exposure={},
        genre_exposure={},
        question_type_exposure={},
        item_exposure={},
        allowed_topics=None,
        preferred_competencies=None,
        first_passage=False,
    )
    assert passage_id not in captured


def test_health_summary_distinguishes_starter_saved_ai_and_ready(project_root, tmp_path):
    bank = _overlay_bank(project_root, tmp_path)
    health = bank.health_summary()
    for skill in ("reading", "listening"):
        data = health[skill]
        assert data["starter_passages"] + data["saved_ai_passages"] == data["passages"]
        assert data["ready_passages"] == data["operational_passages"]
        assert data["ready_starter_passages"] + data["ready_ai_passages"] == data["ready_passages"]
    assert health["generated_passages"] == 0


def test_bank_only_selection_does_not_write_generated_overlay(project_root, tmp_path, monkeypatch):
    import ui.callbacks as callbacks
    from core.session import create_session

    overlay = tmp_path / "generated_items.jsonl"
    overlay.write_text("", encoding="utf-8")
    bank = ItemBank(
        [project_root / "data/starter_items.jsonl", overlay],
        writable_path=overlay,
    ).load()
    monkeypatch.setattr(callbacks, "BANK", bank)

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
        content_source="bank_only",
    )
    before = overlay.read_bytes()
    bundle = callbacks._bank_bundle(state)
    after = overlay.read_bytes()

    assert bundle.passage.id in bank.passages
    assert before == after
    assert bank.health_summary()["generated_passages"] == 0
    assert "does not write" in (state.last_content_note or "").lower() or "no record was written" in (state.last_content_note or "").lower()
