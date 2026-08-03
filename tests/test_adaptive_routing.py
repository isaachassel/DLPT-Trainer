from __future__ import annotations

from core.adaptive import (
    adjacent_evidence_ready,
    diagnostic_probe_band,
    initialize_ability,
    should_stop_diagnostic,
    update_ability,
    update_routing_band,
)
from core.models import ResponseRecord
from core.reporting import build_skill_report
from core.session import create_session, select_next_bundle, submit_current_bundle
from core.constants import SIMULATION_MODE_LABEL
from ui.callbacks import mode_controls


def response(level: str, difficulty: float, correct: bool, qid: str, skill: str = "reading") -> ResponseRecord:
    return ResponseRecord(
        session_id="route",
        passage_id="passage",
        question_id=qid,
        skill=skill,
        mode="diagnostic",
        target_ilr=level,
        item_difficulty=difficulty,
        question_type="inference",
        topic="Government and politics",
        genre="news report",
        stem_en="What is the best answer?",
        choices_snapshot={"A": "One", "B": "Two", "C": "Three", "D": "Four"},
        rationale_en="This answer follows directly from the passage evidence.",
        evidence_ru="подтверждающий текст",
        selected_key="A",
        correct_key="A",
        is_correct=correct,
        response_time_seconds=12.0,
    )


def test_high_level_errors_route_down_one_half_level_per_passage():
    estimate = initialize_ability("reading", "3", broad=True, routing_level="3")
    first = [response("3", 2.0, False, f"q{i}") for i in range(3)]
    estimate = update_ability(estimate, first)
    estimate = update_routing_band(estimate, first, "0", "3")
    assert estimate.routing_ilr == "2+"

    second = [response("2+", 1.25, False, f"q{i+3}") for i in range(3)]
    estimate = update_ability(estimate, second)
    estimate = update_routing_band(estimate, second, "0", "3")
    assert estimate.routing_ilr == "2"
    assert [event["to_ilr"] for event in estimate.routing_history] == ["2+", "2"]


def test_single_wrong_answer_does_not_cause_large_route_jump():
    estimate = initialize_ability("reading", "3", broad=True, routing_level="3")
    records = [response("3", 2.0, False, "q1")]
    estimate = update_ability(estimate, records)
    estimate = update_routing_band(estimate, records, "0", "3")
    assert estimate.routing_ilr == "3"


def test_route_respects_configured_floor_and_ceiling():
    estimate = initialize_ability("reading", "2", broad=True, routing_level="2")
    wrong = [response("2", 0.5, False, f"q{i}") for i in range(8)]
    estimate = update_ability(estimate, wrong)
    estimate = update_routing_band(estimate, wrong, "2", "3")
    assert estimate.routing_ilr == "2"

    estimate = initialize_ability("reading", "3", broad=True, routing_level="3")
    correct = [response("3", 2.0, True, f"u{i}") for i in range(8)]
    estimate = update_ability(estimate, correct)
    estimate = update_routing_band(estimate, correct, "0", "3")
    assert estimate.routing_ilr == "3"


def test_diagnostic_medium_start_and_selected_challenge_start_are_distinct():
    common = dict(
        mode="diagnostic",
        selected_skills=["reading"],
        start_level="3",
        target_level="3",
        topics=[],
        competencies=[],
        max_questions_per_skill=20,
        minimum_questions_per_skill=12,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=False,
        replay_allowed=False,
        slow_audio_allowed=False,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
    )
    medium = create_session(**common, adaptive_start_policy="medium")
    selected = create_session(**common, adaptive_start_policy="selected")
    assert medium.reading_ability.routing_ilr == "2"
    assert selected.reading_ability.routing_ilr == "3"


def test_bank_selection_honors_hard_ilr_range_and_current_route(bank):
    state = create_session(
        mode="training",
        selected_skills=["reading"],
        start_level="3",
        target_level="3",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_of_passage",
        hints_enabled=False,
        transcript_review_enabled=False,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
        adaptive_start_policy="selected",
        minimum_ilr="2",
        maximum_ilr="3",
    )
    bundle = select_next_bundle(state, bank)
    assert {question.target_ilr for question in bundle.questions} == {"3"}

    answers = {question.id: next(key for key in question.choices if key != question.correct_key) for question in bundle.questions}
    submit_current_bundle(state, bundle.passage, bundle.questions, answers, "nonce-1")
    assert state.reading_ability.routing_ilr == "2+"

    next_bundle = select_next_bundle(state, bank)
    assert {question.target_ilr for question in next_bundle.questions} == {"2+"}
    assert all(question.target_ilr in {"2", "2+", "3"} for question in next_bundle.questions)


def test_reading_and_listening_routing_remain_independent():
    state = create_session(
        mode="diagnostic",
        selected_skills=["reading", "listening"],
        start_level="3",
        target_level="3",
        topics=[],
        competencies=[],
        max_questions_per_skill=20,
        minimum_questions_per_skill=12,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=False,
        replay_allowed=False,
        slow_audio_allowed=False,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
        adaptive_start_policy="selected",
    )
    reading_records = [response("3", 2.0, False, f"r{i}") for i in range(3)]
    updated = update_ability(state.reading_ability, reading_records)
    state.reading_ability = update_routing_band(updated, reading_records)
    assert state.reading_ability.routing_ilr == "2+"
    assert state.listening_ability.routing_ilr == "3"


def test_report_contains_adaptive_route_path(bank):
    state = create_session(
        mode="training",
        selected_skills=["reading"],
        start_level="3",
        target_level="3",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_of_passage",
        hints_enabled=False,
        transcript_review_enabled=False,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Starter-bank eSpeak voice",
        speech_rate_label="Normal",
        adaptive_start_policy="selected",
        minimum_ilr="2",
        maximum_ilr="3",
    )
    bundle = select_next_bundle(state, bank)
    answers = {question.id: next(key for key in question.choices if key != question.correct_key) for question in bundle.questions}
    submit_current_bundle(state, bundle.passage, bundle.questions, answers, "nonce-report")
    report = build_skill_report(state, "reading", bank)
    assert "Adaptive routing review" in report
    assert "Passage routing path" in report
    assert "ILR 3 → ILR 2+" in report
    assert "Range-limited interpretation" in report


def test_diagnostic_requires_adjacent_band_evidence_before_precision_stop():
    estimate = initialize_ability("reading", "2", broad=True, routing_level="2")
    same_band = [response("2", 0.5, i % 2 == 0, f"same{i}") for i in range(16)]
    estimate = update_ability(estimate, same_band)
    # Force a small SE to isolate the evidence-balance stopping rule.
    estimate = estimate.model_copy(update={"standard_error": 0.30})
    assert not adjacent_evidence_ready(estimate, "0", "3")
    assert not should_stop_diagnostic(estimate, 12, 20, "0", "3")

    adjacent = [response("2+", 1.25, False, "adj1"), response("2+", 1.25, True, "adj2")]
    estimate = update_ability(estimate, adjacent)
    estimate = estimate.model_copy(update={"standard_error": 0.30, "routing_ilr": "2"})
    assert adjacent_evidence_ready(estimate, "0", "3")
    assert should_stop_diagnostic(estimate, 12, 20, "0", "3")


def test_diagnostic_probe_targets_under_sampled_adjacent_boundary():
    estimate = initialize_ability("reading", "2", broad=True, routing_level="2")
    records = [response("2", 0.5, True, "p1"), response("2", 0.5, False, "p2")]
    estimate = update_ability(estimate, records)
    probe = diagnostic_probe_band(estimate, "0", "3")
    assert probe in {"1+", "2+"}
    assert probe != "2"


def test_mode_controls_hide_unused_start_and_target_fields():
    training = mode_controls("Training Mode", "Reading")
    diagnostic = mode_controls("Adaptive Diagnostic", "Reading")
    simulation = mode_controls(SIMULATION_MODE_LABEL, "Reading")
    assert training[-2]["visible"] is True and training[-1]["visible"] is True
    assert diagnostic[-2]["visible"] is True and diagnostic[-1]["visible"] is False
    assert simulation[-2]["visible"] is False and simulation[-1]["visible"] is False
