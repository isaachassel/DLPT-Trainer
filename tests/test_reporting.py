from __future__ import annotations
from core.reporting import build_full_report
from core.session import create_session, select_next_bundle, submit_current_bundle
from core.scoring import accuracy, item_level_label


def make_completed_piece(bank, mode="training", skill="reading"):
    state = create_session(
        mode=mode, selected_skills=[skill], start_level="1+", target_level="2", topics=[], competencies=[],
        max_questions_per_skill=8, minimum_questions_per_skill=8, timer_mode="off", time_limit_seconds_per_skill=None,
        profile_id=None, feedback_mode="end_only", hints_enabled=False, transcript_review_enabled=True,
        replay_allowed=mode=="training", slow_audio_allowed=mode=="training", voice_label="Starter", speech_rate_label="Normal",
        shortened_simulation=mode=="simulation", simulation_full=False,
    )
    bundle = select_next_bundle(state, bank)
    if skill == "listening":
        state.current_listening_plays = 1
    answers = {q.id:q.correct_key for q in bundle.questions}
    submit_current_bundle(state, bundle.passage, bundle.questions, answers, "x")
    return state


def test_report_calculations_are_correct(bank):
    state = make_completed_piece(bank)
    correct, total, pct = accuracy(state.responses)
    assert correct == total and pct == 1.0
    report = build_full_report(state, bank)
    assert f"{correct} correct" in report


def test_report_uses_provisional_language(bank):
    report = build_full_report(make_completed_piece(bank), bank)
    assert "Provisional" in report or "Insufficient evidence" in report
    assert "official DLPT score" in report


def test_short_simulation_report_is_labeled(bank):
    report = build_full_report(make_completed_piece(bank, mode="simulation"), bank)
    assert "shortened simulation" in report.lower()


def test_training_review_displays_correct_evidence(bank):
    state = make_completed_piece(bank)
    state.responses[0].is_correct = False
    report = build_full_report(state, bank)
    assert state.responses[0].evidence_ru in report


def test_final_report_reveals_level_for_every_completed_question(bank):
    state = make_completed_piece(bank)
    report = build_full_report(state, bank)
    assert "Question-level ILR review" in report
    for record in state.responses:
        assert item_level_label(record) in report


def test_provisional_level_label_is_transparent(bank):
    state = make_completed_piece(bank)
    record = state.responses[0]
    assert record.provisional_item is True
    label = item_level_label(record)
    assert f"Intended ILR {record.target_ilr}" in label
    assert "provisional" in label.lower()


def test_calibrated_level_label_distinguishes_authoring_target(bank):
    state = make_completed_piece(bank)
    record = state.responses[0].model_copy(update={
        "provisional_item": False,
        "target_ilr": "1",
        "item_difficulty": 1.22,
    })
    label = item_level_label(record)
    assert "Approximately ILR 2+" in label
    assert "original authoring target ILR 1" in label
