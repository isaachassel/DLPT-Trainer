from __future__ import annotations
import time
import pytest

from core.session import (
    SessionFlowError, advance_skill_or_finish, create_session, mark_listening_play,
    record_answer_change, select_next_bundle, skill_is_complete, submit_current_bundle,
)
from core.models import UserHistory


def make_state(mode="training", skills=None, max_q=8, timer="off", deadline=None):
    return create_session(
        mode=mode, selected_skills=skills or ["reading"], start_level="1+", target_level="2",
        topics=[], competencies=[], max_questions_per_skill=max_q, minimum_questions_per_skill=min(8,max_q),
        timer_mode=timer, time_limit_seconds_per_skill=deadline, profile_id=None,
        feedback_mode="end_only", hints_enabled=False, transcript_review_enabled=True,
        replay_allowed=mode=="training", slow_audio_allowed=mode=="training",
        voice_label="Starter-bank eSpeak voice", speech_rate_label="Normal",
        simulation_full=mode=="simulation" and max_q>=35, shortened_simulation=mode=="simulation" and max_q<35,
    )


def test_item_bank_prevents_repeats_within_session(bank):
    state = make_state()
    first = select_next_bundle(state, bank)
    state.completed_passage_ids.append(first.passage.id)
    second = select_next_bundle(state, bank)
    assert first.passage.id != second.passage.id


def test_user_history_prevents_unwanted_repeat(bank):
    state = make_state()
    history = UserHistory(profile_id="x", seen_passage_ids=["r009"])
    bundle = select_next_bundle(state, bank, history)
    assert bundle.passage.id != "r009"


def test_all_questions_must_be_answered(bank):
    state = make_state()
    bundle = select_next_bundle(state, bank)
    with pytest.raises(SessionFlowError, match="Answer every question"):
        submit_current_bundle(state, bundle.passage, bundle.questions, {}, "n1")


def test_ca_mode_prevents_old_passage_resubmission(bank):
    state = make_state("simulation", max_q=12)
    bundle = select_next_bundle(state, bank)
    answers = {q.id: q.correct_key for q in bundle.questions}
    submit_current_bundle(state, bundle.passage, bundle.questions, answers, "n1")
    with pytest.raises(SessionFlowError, match="does not match"):
        submit_current_bundle(state, bundle.passage, bundle.questions, answers, "n2")


def test_duplicate_callback_nonce_does_not_duplicate_responses(bank):
    state = make_state()
    bundle = select_next_bundle(state, bank)
    answers = {q.id: q.correct_key for q in bundle.questions}
    first = submit_current_bundle(state, bundle.passage, bundle.questions, answers, "same")
    count = len(state.responses)
    second = submit_current_bundle(state, bundle.passage, bundle.questions, answers, "same")
    assert first and second == [] and len(state.responses) == count


def test_answer_change_behavior_is_tracked(bank):
    state = make_state()
    bundle = select_next_bundle(state, bank)
    qid = bundle.questions[0].id
    record_answer_change(state, qid, "A")
    record_answer_change(state, qid, "B")
    assert state.current_answer_changes[qid] == 1


def test_strict_listening_playback_cannot_replay():
    state = make_state("simulation", ["listening"], max_q=12)
    mark_listening_play(state)
    with pytest.raises(SessionFlowError, match="Replay is disabled"):
        mark_listening_play(state)


def test_training_mode_replay_works():
    state = make_state("training", ["listening"])
    mark_listening_play(state)
    mark_listening_play(state)
    assert state.current_listening_plays == 2


def test_strict_timer_expires():
    state = make_state("simulation", max_q=12, timer="strict", deadline=1)
    state.skill_deadline_epoch = time.time() - 1
    bundle = select_next_bundle(make_state("simulation", max_q=12), __import__('ui.callbacks', fromlist=['BANK']).BANK)
    state.current_passage_id = bundle.passage.id
    state.current_question_ids = [q.id for q in bundle.questions]
    with pytest.raises(SessionFlowError, match="Time expired"):
        submit_current_bundle(state, bundle.passage, bundle.questions, {q.id:q.correct_key for q in bundle.questions}, "x")


def test_standard_timer_does_not_enforce_deadline(bank):
    state = make_state("training", timer="standard")
    bundle = select_next_bundle(state, bank)
    records = submit_current_bundle(state, bundle.passage, bundle.questions, {q.id:q.correct_key for q in bundle.questions}, "x")
    assert records


def test_full_simulation_requires_at_least_35_questions():
    state = make_state("simulation", max_q=35)
    assert not skill_is_complete(state)
    assert state.simulation_full


def test_short_simulation_is_clearly_flagged():
    state = make_state("simulation", max_q=12)
    assert state.shortened_simulation and not state.simulation_full


def test_reading_and_listening_sections_advance_independently():
    state = make_state("training", ["reading", "listening"], max_q=1)
    state.responses.append(__import__('tests.test_adaptive', fromlist=['response']).response("reading", True, qid="advance"))
    assert advance_skill_or_finish(state) is False
    assert state.active_skill == "listening"
    assert state.listening_ability.items_answered == 0
