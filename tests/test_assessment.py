from __future__ import annotations

import pytest

from core import assessment
from core.adaptive import response_probability
from core.constants import ILR_THETA
from core.models import SessionState
from core.reporting import build_full_report
from core.session import (SessionFlowError, advance_skill_or_finish, create_session,
                          mark_listening_play, select_next_bundle, submit_current_bundle)
from core.storage import LocalStorage
from tests.test_adaptive import response


def state_for(skills=None, **kwargs):
    options = dict(mode="assessment", selected_skills=skills or ["reading"], start_level="0",
                   target_level="3", topics=[], competencies=[], max_questions_per_skill=1,
                   minimum_questions_per_skill=0, timer_mode="off", time_limit_seconds_per_skill=None,
                   profile_id=None, feedback_mode="end_of_passage", hints_enabled=True,
                   transcript_review_enabled=True, replay_allowed=True, slow_audio_allowed=True,
                   voice_label="Starter", speech_rate_label="Normal")
    options.update(kwargs)
    return create_session(**options)


def answer(state, bundle, correct=True):
    if bundle.passage.skill == "listening":
        mark_listening_play(state)
    choices = {q.id: q.correct_key if correct else next(k for k in q.choices if k != q.correct_key)
               for q in bundle.questions}
    return submit_current_bundle(state, bundle.passage, bundle.questions, choices, bundle.passage.id)


def synthetic_records(passage, pattern, level="1+"):
    return [response("reading", correct, ILR_THETA[level], f"{passage}-{i}").model_copy(
        update={"passage_id": str(passage), "target_ilr": level, "mode": "assessment"})
        for i, correct in enumerate(pattern)]


def test_strong_weak_mixed_and_borderline_posteriors():
    estimates = {}
    for name, pattern in {"strong": [True]*3, "weak": [False]*3,
                          "mixed": [True, False, True], "borderline": [True, True, True, False]}.items():
        estimate = assessment.initialize("reading")
        for n in range(12):
            estimate = assessment.update(estimate, synthetic_records(n, pattern))
        estimates[name] = estimate
        assert sum(estimate.posterior_weights) == pytest.approx(1)
        assert estimate.ci_low < estimate.theta < estimate.ci_high
    assert estimates["weak"].theta < estimates["mixed"].theta < estimates["borderline"].theta < estimates["strong"].theta
    # 75% on the 1+ anchor lies close to its upper boundary under guessing.
    borderline = estimates["borderline"]
    boundary = (ILR_THETA["1+"] + ILR_THETA["2"]) / 2
    assert borderline.ci_low < boundary < borderline.ci_high
    assert max(assessment.band_probabilities(borderline).values()) < 0.60


def test_shared_passage_provides_less_information_than_independent_passages():
    grouped = assessment.initialize("reading")
    independent = assessment.initialize("reading")
    for n in range(6):
        grouped = assessment.update(grouped, synthetic_records(n, [True, True, False]))
        for j, correct in enumerate([True, True, False]):
            independent = assessment.update(independent, synthetic_records(f"{n}-{j}", [correct]))
    assert grouped.standard_error > independent.standard_error


def test_guessing_is_explicit_and_chance_performance_is_not_medium_ability():
    assert response_probability(-100, 0) == pytest.approx(0.25)
    estimate = assessment.initialize("reading")
    for n in range(10):
        estimate = assessment.update(estimate, synthetic_records(n, [True, False, False, False]))
    assert estimate.theta < ILR_THETA["1"]


@pytest.mark.parametrize("correct", [True, False])
def test_actual_bank_routes_and_never_repeats(bank, correct):
    state = state_for(assessment_min_passages=12, assessment_max_passages=12)
    levels = []
    while state.status == "active":
        bundle = select_next_bundle(state, bank)
        levels.append(ILR_THETA[bundle.questions[0].target_ilr])
        answer(state, bundle, correct)
        advance_skill_or_finish(state)
    assert len(state.completed_passage_ids) == len(set(state.completed_passage_ids)) == 12
    assert max(levels[1:]) > levels[0] if correct else min(levels[1:]) < levels[0]
    assert state.assessment_end_reasons == {"reading": "maximum"}


def test_skill_separation_and_whole_passage_limits(bank):
    state = state_for(["reading", "listening"], assessment_min_passages=2, assessment_max_passages=2)
    initial_listening = state.listening_ability.model_dump()
    for _ in range(2):
        bundle = select_next_bundle(state, bank)
        assert len(bundle.questions) == len(bank.get_questions(bundle.passage.id)) > 1
        answer(state, bundle)
        advance_skill_or_finish(state)
    assert state.active_skill == "listening"
    assert state.listening_ability.model_dump() == initial_listening
    reading = state.reading_ability.model_dump()
    for _ in range(2):
        answer(state, select_next_bundle(state, bank), False)
        advance_skill_or_finish(state)
    assert state.reading_ability.model_dump() == reading
    assert state.status == "completed"


def test_minimum_precision_and_maximum_stopping():
    state = state_for(assessment_min_passages=3, assessment_max_passages=4)
    state.reading_ability.standard_error = 0.4
    state.reading_ability.evidence_by_ilr = {"1+": 3, "2": 3}
    for n in range(2):
        state.responses.extend(synthetic_records(n, [True]*3))
    assert assessment.stop_reason(state, "reading") is None
    state.responses.extend(synthetic_records(2, [True]*3))
    assert assessment.stop_reason(state, "reading") == "precision"
    state.reading_ability.evidence_by_ilr = {"1+": 9}
    assert assessment.stop_reason(state, "reading") is None
    state.responses.extend(synthetic_records(3, [True]*3))
    assert assessment.stop_reason(state, "reading") == "maximum"


@pytest.mark.parametrize("options", [dict(assessment_min_passages=8, assessment_max_passages=2),
                                    dict(assessment_min_passages=1), dict(assessment_target_sd=0.1)])
def test_invalid_limits_rejected(options):
    with pytest.raises(ValueError):
        state_for(**options)


@pytest.fixture
def callbacks(monkeypatch, tmp_path, bank):
    from ui import callbacks as cb
    monkeypatch.setattr(cb, "BANK", bank)
    monkeypatch.setattr(cb, "STORAGE", LocalStorage(tmp_path / "sessions", tmp_path / "history"))
    monkeypatch.setattr(cb, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(cb, "_prefetch_selected_playback", lambda *a: None)
    return cb


def start(cb, skill="Reading", **kwargs):
    return cb.start_session_callback("Adaptive Assessment", skill, "1+", "2", "Complete passages", "Off",
                                    [], [], "After each passage", True, True, "Starter", "Normal", "", **kwargs)


def submit_render(cb, rendered, correct=True):
    state, data, nonce = rendered[:3]
    values = [q["correct_key"] if correct else next(k for k in q["choices"] if k != q["correct_key"])
              for q in data["questions"]]
    if state.active_skill == "listening":
        cb.confirm_audio_playback_callback(state, data)
    return cb.submit_passage_callback(state, data, nonce, *(values + [None]*(5-len(values))))


def test_ui_assessment_end_review_duplicate_submit_and_checkpoint(callbacks):
    cb = callbacks
    rendered = start(cb, assessment_min_passages=2, assessment_max_passages=2)
    state = rendered[0]
    assert state.mode == "assessment" and not state.hints_enabled and state.feedback_mode == "end_only"
    first = rendered
    explanation = rendered[1]["questions"][0]["rationale_en"]
    rendered = submit_render(cb, rendered)
    assert not rendered[26]["visible"] and not rendered[27]["visible"]
    assert explanation not in build_full_report(state, cb.BANK)
    # The checkpoint preserves the posterior and the shuffled current questions.
    restored = cb.resume_session_callback(state.session_id)
    assert restored[1] == rendered[1]
    assert restored[0].reading_ability.posterior_weights == state.reading_ability.posterior_weights
    before = len(state.responses)
    submit_render(cb, first)
    assert len(state.responses) == before
    rendered = submit_render(cb, rendered, False)
    assert state.status == "completed"
    assert "maximum" in rendered[27]["value"].lower()
    assert explanation in rendered[27]["value"]
    assert "90% posterior" in rendered[27]["value"]
    again = cb.resume_session_callback(state.session_id)
    assert again[27]["value"] == rendered[27]["value"]


@pytest.mark.parametrize("available", [0, 1])
def test_sparse_bank_finishes_explicitly(callbacks, monkeypatch, available):
    cb = callbacks
    passages = cb.BANK.active_passages("reading", "ru")[:available]
    monkeypatch.setattr(cb.BANK, "active_passages", lambda *a: passages)
    rendered = start(cb)
    if available:
        rendered = submit_render(cb, rendered)
    state = rendered[0]
    assert state.status == "completed"
    assert state.assessment_end_reasons["reading"] == "content_exhausted"
    assert "Insufficient evidence" in rendered[27]["value"]
    assert "no estimated practice ILR" in rendered[27]["value"]


def test_exhausted_reading_continues_listening_without_revealing_results(callbacks, monkeypatch):
    cb = callbacks
    original = cb.BANK.active_passages
    monkeypatch.setattr(cb.BANK, "active_passages", lambda skill, language: [] if skill == "reading" else original(skill, language))
    rendered = start(cb, "Reading + Listening (separate sections)", assessment_min_passages=2, assessment_max_passages=2)
    assert rendered[0].active_skill == "listening"
    assert not rendered[27]["visible"]
    for _ in range(2):
        rendered = submit_render(cb, rendered)
    assert rendered[0].assessment_end_reasons == {"reading": "content_exhausted", "listening": "maximum"}


def test_listening_requires_playback_and_withholds_transcript(callbacks):
    cb = callbacks
    rendered = start(cb, "Listening")
    state, data = rendered[:2]
    assert data["passage"]["passage_ru"] not in rendered[6]["value"]
    bundle = cb._bundle_from_dict(data)
    with pytest.raises(SessionFlowError, match="Play"):
        submit_current_bundle(state, bundle.passage, bundle.questions,
                              {q.id: q.correct_key for q in bundle.questions}, "test")
    cb.confirm_audio_playback_callback(state, data)
    with pytest.raises(SessionFlowError, match="Replay"):
        mark_listening_play(state)
    playback = cb.play_audio_callback(state, data)
    assert "Replay is disabled" in playback[3]["value"]


def test_boundary_report_is_inconclusive(bank):
    state = state_for(assessment_min_passages=2, assessment_max_passages=12)
    for n in range(12):
        records = synthetic_records(n, [True, True, True, False])
        state.responses.extend(records)
        state.reading_ability = assessment.update(state.reading_ability, records)
    state.status = "completed"
    state.assessment_end_reasons["reading"] = "maximum"
    report = build_full_report(state, bank)
    assert "Estimated practice ILR" in report and "Inconclusive classification" in report


def test_no_duplicate_text_under_different_ids(bank, monkeypatch):
    passage = bank.active_passages("reading", "ru")[0]
    duplicate = passage.model_copy(update={"id": "duplicate-text"})
    state = state_for()
    state.completed_passage_ids.append(passage.id)
    monkeypatch.setattr(bank, "active_passages", lambda *a: [duplicate])
    monkeypatch.setattr(bank, "get_questions", lambda *a: [next(iter(bank.questions.values()))])
    with pytest.raises(LookupError):
        assessment.select(state, bank)


@pytest.mark.parametrize("language", ["ru", "zh-CN"])
@pytest.mark.parametrize("skill", ["reading", "listening"])
def test_all_supported_language_skill_banks(bank, language, skill):
    state = state_for([skill], language=language)
    bundle = select_next_bundle(state, bank)
    assert bundle.passage.language == language and bundle.passage.skill == skill
    answer(state, bundle)
    assert state.ability_for(skill).items_answered == len(bundle.questions)


def test_checkpoint_schema_is_backward_compatible():
    data = state_for().model_dump()
    for key in list(data):
        if key.startswith("assessment_"):
            data.pop(key)
    restored = SessionState.model_validate(data)
    assert restored.assessment_min_passages == 6


def test_computed_posterior_reaches_precision_after_sustained_evidence():
    state = state_for(assessment_min_passages=6, assessment_max_passages=40)
    stopped = None
    for n in range(40):
        records = synthetic_records(n, [True, True, False], level="1+" if n % 2 else "2")
        state.responses.extend(records)
        state.reading_ability = assessment.update(state.reading_ability, records)
        stopped = assessment.stop_reason(state, "reading")
        if stopped:
            break
    assert stopped == "precision"
    assert 6 <= assessment.passage_count(state, "reading") < 40
    assert state.reading_ability.standard_error <= 0.55


def test_mislabeled_calibration_fields_do_not_control_assessment(bank):
    state = state_for()
    bundle = select_next_bundle(state, bank)
    questions = [q.model_copy(update={"calibrated_difficulty": 99.0, "discrimination": 3.0})
                 for q in bundle.questions]
    records = submit_current_bundle(state, bundle.passage, questions,
                                    {q.id: q.correct_key for q in questions}, "calibration")
    assert all(r.provisional_item and r.item_discrimination == 1 for r in records)
    assert all(r.item_difficulty == ILR_THETA[r.target_ilr] for r in records)


def test_resume_after_scoring_before_section_advance(callbacks):
    cb = callbacks
    state = state_for(["reading", "listening"], assessment_min_passages=2, assessment_max_passages=2)
    for _ in range(2):
        answer(state, select_next_bundle(state, cb.BANK))
    assert state.active_skill == "reading" and state.current_passage_id is None
    cb.STORAGE.save_checkpoint(state)
    rendered = cb.resume_session_callback(state.session_id)
    restored = rendered[0]
    assert restored.active_skill == "listening"
    assert restored.assessment_end_reasons["reading"] == "maximum"
    assert len(restored.responses) == len(state.responses)
    assert not rendered[27]["visible"]


def test_early_exit_preserves_reason_on_resume(callbacks):
    cb = callbacks
    rendered = start(cb)
    rendered = submit_render(cb, rendered)
    state = rendered[0]
    ended = cb.abandon_strict_callback(state, True)
    assert state.status == "stopped"
    assert state.assessment_end_reasons == {"reading": "abandoned"}
    assert "Insufficient evidence" in ended[27]["value"]
    restored = cb.resume_session_callback(state.session_id)
    assert restored[0].status == "stopped" and restored[1] is None


def test_invalid_hidden_assessment_controls_do_not_break_training(callbacks):
    result = callbacks.start_session_callback("Training Mode", "Reading", "1+", "2", "Short — 8 questions", "Off",
                                              [], [], "After each passage", False, True, "Starter", "Normal", "",
                                              assessment_min_passages=10, assessment_max_passages=2)
    assert result[0].mode == "training" and result[1]
