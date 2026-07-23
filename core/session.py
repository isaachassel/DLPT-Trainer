from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from .adaptive import initialize_ability, should_stop_diagnostic, update_ability
from .constants import ILR_THETA, SIMULATION_MIN_QUESTIONS
from .item_bank import ItemBank, shuffled_bundle
from .models import PassageItem, QuestionItem, ResponseRecord, SessionState, UserHistory


class SessionFlowError(RuntimeError):
    pass


@dataclass
class PassageBundle:
    passage: PassageItem
    questions: list[QuestionItem]


def create_session(
    mode: str,
    selected_skills: list[str],
    start_level: str,
    target_level: str,
    topics: list[str],
    competencies: list[str],
    max_questions_per_skill: int,
    minimum_questions_per_skill: int,
    timer_mode: str,
    time_limit_seconds_per_skill: int | None,
    profile_id: str | None,
    feedback_mode: str,
    hints_enabled: bool,
    transcript_review_enabled: bool,
    replay_allowed: bool,
    slow_audio_allowed: bool,
    voice_label: str,
    speech_rate_label: str,
    content_source: str = "bank_only",
    simulation_full: bool = False,
    shortened_simulation: bool = False,
) -> SessionState:
    now = time.time()
    broad = mode != "training"
    reading = initialize_ability("reading", start_level if mode == "training" else "1+", broad=broad)
    listening = initialize_ability("listening", start_level if mode == "training" else "1+", broad=broad)
    state = SessionState(
        profile_id=profile_id.strip() if profile_id and profile_id.strip() else None,
        mode=mode,
        selected_skills=selected_skills,
        start_level=start_level,
        target_level=target_level,
        topics=topics,
        competencies=competencies,
        max_questions_per_skill=max_questions_per_skill,
        minimum_questions_per_skill=minimum_questions_per_skill,
        simulation_full=simulation_full,
        shortened_simulation=shortened_simulation,
        timer_mode=timer_mode,
        time_limit_seconds_per_skill=time_limit_seconds_per_skill,
        session_started_at_epoch=now,
        skill_started_at_epoch=now,
        skill_deadline_epoch=(now + time_limit_seconds_per_skill) if time_limit_seconds_per_skill else None,
        reading_ability=reading,
        listening_ability=listening,
        feedback_mode=feedback_mode,
        hints_enabled=hints_enabled,
        transcript_review_enabled=transcript_review_enabled,
        replay_allowed=replay_allowed,
        slow_audio_allowed=slow_audio_allowed,
        voice_label=voice_label,
        speech_rate_label=speech_rate_label,
        content_source=content_source,
    )
    return state


def remaining_seconds(state: SessionState, now: float | None = None) -> int | None:
    if state.skill_deadline_epoch is None:
        return None
    return max(0, int(state.skill_deadline_epoch - (now or time.time())))


def ensure_not_expired(state: SessionState, now: float | None = None) -> None:
    remaining = remaining_seconds(state, now)
    if remaining is not None and remaining <= 0:
        state.status = "expired"
        raise SessionFlowError("Time expired for this skill section. Completed passages remain saved.")


def select_next_bundle(state: SessionState, bank: ItemBank, history: UserHistory | None = None) -> PassageBundle:
    ensure_not_expired(state)
    skill = state.active_skill
    estimate = state.ability_for(skill)
    history_seen_passages = set(history.seen_passage_ids) if history else set()
    history_seen_questions = set(history.seen_question_ids) if history else set()
    first_passage = state.completed_count(skill) == 0
    selection = bank.select(
        skill=skill,
        estimate=estimate,
        mode=state.mode,
        target_level=state.target_level,
        seen_passages=set(state.completed_passage_ids) | history_seen_passages,
        seen_questions=set(state.completed_question_ids) | history_seen_questions,
        topic_exposure=state.topic_exposure,
        genre_exposure=state.genre_exposure,
        question_type_exposure=state.question_type_exposure,
        item_exposure=state.item_exposure,
        allowed_topics=set(state.topics) if state.topics else None,
        preferred_competencies=set(state.competencies) if state.competencies else None,
        first_passage=first_passage,
    )
    passage = bank.get_passage(selection.passage_id)
    questions = shuffled_bundle(bank.get_questions(passage.id), seed=f"{state.session_id}:{passage.id}")
    return activate_bundle(state, passage, questions)


def activate_bundle(state: SessionState, passage: PassageItem, questions: list[QuestionItem]) -> PassageBundle:
    """Make a validated passage bundle current without coupling selection to its source."""
    skill = state.active_skill
    if passage.skill != skill:
        raise SessionFlowError(f"Cannot activate a {passage.skill} passage in the {skill} section.")
    remaining_target = state.max_questions_per_skill - state.completed_count(skill)
    if remaining_target > 0 and len(questions) > remaining_target:
        questions = questions[:remaining_target]
    if not questions:
        raise SessionFlowError("No questions remain in the selected bundle.")
    state.current_passage_id = passage.id
    state.current_question_ids = [q.id for q in questions]
    state.current_answers = {}
    state.current_answer_changes = {q.id: 0 for q in questions}
    state.current_listening_plays = 0
    state.current_started_at_epoch = time.time()
    return PassageBundle(passage=passage, questions=questions)


def record_answer_change(state: SessionState, question_id: str, new_key: str) -> None:
    old = state.current_answers.get(question_id)
    if old and old != new_key:
        state.current_answer_changes[question_id] = state.current_answer_changes.get(question_id, 0) + 1
    state.current_answers[question_id] = new_key


def mark_listening_play(state: SessionState) -> None:
    if state.active_skill != "listening":
        return
    if state.mode in {"diagnostic", "simulation"} and state.current_listening_plays >= 1:
        raise SessionFlowError("Replay is disabled in strict listening conditions.")
    state.current_listening_plays += 1


def submit_current_bundle(
    state: SessionState,
    passage: PassageItem,
    questions: list[QuestionItem],
    answers: dict[str, str],
    request_nonce: str,
    now: float | None = None,
) -> list[ResponseRecord]:
    ensure_not_expired(state, now)
    if request_nonce in state.handled_nonces:
        return []
    if passage.id != state.current_passage_id:
        raise SessionFlowError("The submitted passage does not match the active session passage.")
    missing = [q.id for q in questions if not answers.get(q.id)]
    if missing:
        raise SessionFlowError("Answer every question on the current passage before advancing.")
    elapsed = max(0.0, (now or time.time()) - (state.current_started_at_epoch or (now or time.time())))
    per_question_time = elapsed / max(1, len(questions))
    records: list[ResponseRecord] = []
    for question in questions:
        selected = answers[question.id]
        record = ResponseRecord(
            session_id=state.session_id,
            passage_id=passage.id,
            question_id=question.id,
            skill=passage.skill,
            mode=state.mode,
            target_ilr=question.target_ilr,
            item_difficulty=question.operational_difficulty,
            question_type=question.question_type,
            topic=passage.topic,
            genre=passage.genre,
            stem_en=question.stem_en,
            choices_snapshot=question.choices,
            rationale_en=question.rationale_en,
            evidence_ru=question.evidence_ru,
            selected_key=selected,
            correct_key=question.correct_key,
            is_correct=selected == question.correct_key,
            response_time_seconds=per_question_time,
            listening_play_count=state.current_listening_plays,
            answer_change_count=state.current_answer_changes.get(question.id, 0),
            provisional_item=question.calibrated_difficulty is None,
        )
        records.append(record)
    state.responses.extend(records)
    state.completed_passage_ids.append(passage.id)
    state.completed_question_ids.extend(q.id for q in questions)
    state.topic_exposure[passage.topic] = state.topic_exposure.get(passage.topic, 0) + 1
    state.genre_exposure[passage.genre] = state.genre_exposure.get(passage.genre, 0) + 1
    state.item_exposure[passage.id] = state.item_exposure.get(passage.id, 0) + 1
    for question in questions:
        state.question_type_exposure[question.question_type] = state.question_type_exposure.get(question.question_type, 0) + 1
    if passage.skill == "reading":
        state.reading_ability = update_ability(state.reading_ability, records)
    else:
        state.listening_ability = update_ability(state.listening_ability, records)
    state.handled_nonces.append(request_nonce)
    state.handled_nonces = state.handled_nonces[-100:]
    state.current_passage_id = None
    state.current_question_ids = []
    state.current_answers = {}
    return records


def skill_is_complete(state: SessionState, skill: str | None = None) -> bool:
    skill = skill or state.active_skill
    count = state.completed_count(skill)
    estimate = state.ability_for(skill)
    if state.mode == "diagnostic":
        return should_stop_diagnostic(estimate, state.minimum_questions_per_skill, state.max_questions_per_skill)
    if state.mode == "simulation":
        required = state.max_questions_per_skill
        if state.simulation_full:
            required = max(SIMULATION_MIN_QUESTIONS, required)
        return count >= required
    return count >= state.max_questions_per_skill


def advance_skill_or_finish(state: SessionState, now: float | None = None, force: bool = False) -> bool:
    if not force and not skill_is_complete(state):
        return False
    if state.active_skill_index + 1 < len(state.selected_skills):
        state.active_skill_index += 1
        current = now or time.time()
        state.skill_started_at_epoch = current
        state.skill_deadline_epoch = current + state.time_limit_seconds_per_skill if state.time_limit_seconds_per_skill else None
        state.current_passage_id = None
        state.current_question_ids = []
        state.current_answers = {}
        state.current_listening_plays = 0
        return False
    state.status = "completed"
    return True


def update_history(history: UserHistory, state: SessionState) -> UserHistory:
    history.seen_passage_ids = sorted(set(history.seen_passage_ids) | set(state.completed_passage_ids))
    history.seen_question_ids = sorted(set(history.seen_question_ids) | set(state.completed_question_ids))
    history.response_records.extend(state.responses)
    if state.reading_ability.items_answered:
        history.reading_estimates.append(state.reading_ability.model_dump(mode="json"))
    if state.listening_ability.items_answered:
        history.listening_estimates.append(state.listening_ability.model_dump(mode="json"))
    return history
