from __future__ import annotations

from core.session import create_session, select_next_bundle, submit_current_bundle
from ui.callbacks import _passage_feedback, _passage_markdown


def _make_state(bank, mode="training"):
    state = create_session(
        mode=mode, selected_skills=["reading"], start_level="1+", target_level="2",
        topics=[], competencies=[], max_questions_per_skill=(8 if mode == "training" else 20),
        minimum_questions_per_skill=(8 if mode == "training" else 12),
        timer_mode="off", time_limit_seconds_per_skill=None, profile_id=None,
        feedback_mode=("end_of_passage" if mode == "training" else "end_only"),
        hints_enabled=False, transcript_review_enabled=True,
        replay_allowed=mode == "training", slow_audio_allowed=mode == "training",
        voice_label="Starter", speech_rate_label="Normal",
    )
    return state


def test_training_passage_feedback_reveals_item_level(bank):
    state = _make_state(bank, "training")
    bundle = select_next_bundle(state, bank)
    answers = {question.id: question.correct_key for question in bundle.questions}
    records = submit_current_bundle(state, bundle.passage, bundle.questions, answers, "level-disclosure")
    feedback = _passage_feedback(records, bundle.passage, state)
    assert f"Passage authoring target:** ILR {bundle.passage.target_ilr}" in feedback
    for record in records:
        assert f"Intended ILR {record.target_ilr}" in feedback


def test_active_diagnostic_passage_does_not_reveal_level(bank):
    state = _make_state(bank, "diagnostic")
    bundle = select_next_bundle(state, bank)
    rendered = _passage_markdown(bundle, state)
    assert f"ILR {bundle.passage.target_ilr}" not in rendered
