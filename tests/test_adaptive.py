from __future__ import annotations
from collections import Counter

from core.adaptive import initialize_ability, score_passage, update_ability
from core.models import ResponseRecord


def response(skill: str, correct: bool, difficulty: float = 0.0, qid: str = "q") -> ResponseRecord:
    return ResponseRecord(
        session_id="s", passage_id="p", question_id=qid, skill=skill, mode="diagnostic",
        target_ilr="1+", item_difficulty=difficulty, question_type="main idea", topic="T", genre="G",
        stem_en="Question?", choices_snapshot={"A":"One","B":"Two","C":"Three","D":"Four"},
        rationale_en="A sufficiently detailed explanation.", evidence_ru="текст", selected_key="A",
        correct_key="A", is_correct=correct, response_time_seconds=10,
    )


def test_reading_listening_estimates_remain_independent():
    reading = initialize_ability("reading")
    listening = initialize_ability("listening")
    reading2 = update_ability(reading, [response("reading", True, 0.5, str(i)) for i in range(8)])
    assert reading2.theta > reading.theta
    assert listening.theta == initialize_ability("listening").theta
    assert listening.items_answered == 0


def test_uncertainty_decreases_with_useful_evidence():
    estimate = initialize_ability("reading")
    updated = update_ability(estimate, [response("reading", i % 3 != 0, 0.0, str(i)) for i in range(16)])
    assert updated.standard_error < estimate.standard_error


def test_target_level_influences_training_score(bank):
    estimate = initialize_ability("reading", "1+", broad=False)
    passage = bank.get_passage("r006")
    questions = bank.get_questions(passage.id)
    common = dict(topic_exposure=Counter(), genre_exposure=Counter(), question_type_exposure=Counter(), item_exposure=Counter())
    matching = score_passage(passage, questions, estimate, "training", "2+", **common)
    distant = score_passage(passage, questions, estimate, "training", "0", **common)
    assert matching.score > distant.score


def test_content_balance_penalizes_overused_topic(bank):
    estimate = initialize_ability("reading")
    passage = bank.get_passage("r005")
    questions = bank.get_questions(passage.id)
    balanced = score_passage(passage, questions, estimate, "diagnostic", "2", Counter(), Counter(), Counter(), Counter())
    overused = score_passage(passage, questions, estimate, "diagnostic", "2", Counter({passage.topic: 5, "Other": 0}), Counter(), Counter(), Counter())
    assert overused.score < balanced.score


def test_exposure_controls_reduce_selection_score(bank):
    estimate = initialize_ability("reading")
    passage = bank.get_passage("r005")
    questions = bank.get_questions(passage.id)
    fresh = score_passage(passage, questions, estimate, "diagnostic", "2", Counter(), Counter(), Counter(), Counter())
    exposed = score_passage(passage, questions, estimate, "diagnostic", "2", Counter(), Counter(), Counter(), Counter({passage.id: 3}))
    assert exposed.score < fresh.score
