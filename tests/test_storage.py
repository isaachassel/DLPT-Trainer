from __future__ import annotations
import json
from pathlib import Path
import pytest

from core.session import create_session, select_next_bundle, submit_current_bundle
from core.storage import LocalStorage, StorageError, export_responses_csv, export_session_json, safe_filename


def state_with_response(bank):
    state = create_session(
        mode="training", selected_skills=["reading"], start_level="1+", target_level="2", topics=[], competencies=[],
        max_questions_per_skill=8, minimum_questions_per_skill=8, timer_mode="off", time_limit_seconds_per_skill=None,
        profile_id=None, feedback_mode="end_only", hints_enabled=False, transcript_review_enabled=True,
        replay_allowed=True, slow_audio_allowed=True, voice_label="Starter", speech_rate_label="Normal",
    )
    bundle = select_next_bundle(state, bank)
    submit_current_bundle(state, bundle.passage, bundle.questions, {q.id:q.correct_key for q in bundle.questions}, "n")
    return state


def test_session_recovery_preserves_completed_responses(tmp_path, bank):
    storage = LocalStorage(tmp_path/"sessions", tmp_path/"history")
    state = state_with_response(bank)
    storage.save_checkpoint(state)
    restored = storage.load_checkpoint(state.session_id)
    assert len(restored.responses) == len(state.responses)
    assert restored.completed_passage_ids == state.completed_passage_ids


def test_checkpoint_can_be_restored(tmp_path, bank):
    storage = LocalStorage(tmp_path/"sessions", tmp_path/"history")
    state = state_with_response(bank)
    path = storage.save_checkpoint(state)
    assert path.exists() and storage.load_checkpoint(state.session_id).session_id == state.session_id


def test_corrupted_checkpoint_fails_safely(tmp_path, bank):
    storage = LocalStorage(tmp_path/"sessions", tmp_path/"history")
    state = state_with_response(bank)
    path = storage.save_checkpoint(state)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(StorageError, match="corrupted"):
        storage.load_checkpoint(state.session_id)


def test_exported_json_and_csv_contain_records(tmp_path, bank):
    state = state_with_response(bank)
    json_path = export_session_json(state, tmp_path)
    csv_path = export_responses_csv(state, tmp_path)
    assert state.session_id in json_path.read_text(encoding="utf-8")
    text = csv_path.read_text(encoding="utf-8")
    assert "question_id" in text and state.responses[0].question_id in text


def test_export_filename_is_sanitized():
    assert safe_filename("../../bad name;rm") == "bad_name_rm"
