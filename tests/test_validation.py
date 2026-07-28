from __future__ import annotations
from core.models import QuestionItem
from core.validation import validate_question


def test_starter_item_bank_passes_validation(bank):
    assert bank.validate_operational_bank() == []


def test_invalid_ambiguous_items_are_rejected(bank):
    passage = bank.get_passage("r005")
    q = bank.get_questions(passage.id)[0]
    bad = q.model_copy(update={"choices": {"A":"Same", "B":"Same", "C":"Other", "D":"Last"}})
    report = validate_question(bad, passage)
    assert report.status == "rejected"


def test_reading_bundle_constraints(bank):
    sizes = {len(bank.get_questions(p.id)) for p in bank.active_passages("reading")}
    assert sizes.issubset({1,2,3,4,5}) and {3,4,5}.issubset(sizes)


def test_listening_bundle_constraints(bank):
    sizes = {len(bank.get_questions(p.id)) for p in bank.active_passages("listening")}
    assert sizes.issubset({1,2,3}) and {2,3}.issubset(sizes)


def test_starter_bank_supports_full_simulation_counts(bank):
    reading = sum(len(bank.get_questions(p.id)) for p in bank.active_passages("reading"))
    listening = sum(len(bank.get_questions(p.id)) for p in bank.active_passages("listening"))
    assert reading >= 35 and listening >= 35


def test_parallel_answer_frames_are_not_false_near_duplicates(bank):
    passage = bank.get_passage("r005")
    question = bank.get_questions(passage.id)[0]
    parallel = question.model_copy(update={
        "choices": {
            "A": "The road will open on Monday",
            "B": "The road will close on Monday",
            "C": "The road will remain unchanged on Monday",
            "D": "The road will be inspected on Monday",
        },
        "correct_key": "A",
    })
    report = validate_question(parallel, passage)
    assert report.deterministic_checks["no_near_duplicate_choices"] is True


def test_tiny_qualifier_change_is_rejected_as_near_duplicate(bank):
    passage = bank.get_passage("r005")
    question = bank.get_questions(passage.id)[0]
    duplicate = question.model_copy(update={
        "choices": {
            "A": "The class begins on Monday",
            "B": "The class begins on Monday only",
            "C": "The class begins on Tuesday",
            "D": "The class has been canceled",
        },
        "correct_key": "A",
    })
    report = validate_question(duplicate, passage)
    assert report.deterministic_checks["no_near_duplicate_choices"] is False
