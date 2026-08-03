from __future__ import annotations
import random
from core.item_bank import shuffle_question, shuffled_bundle
from core.validation import answer_position_balance, bank_balance_passes


def test_answer_choices_are_shuffled(bank):
    q = bank.questions["r001_q1"]
    shuffled = shuffle_question(q, random.Random(4))
    assert list(shuffled.choices.values()) != list(q.choices.values())


def test_correct_key_is_remapped_after_shuffle(bank):
    q = bank.questions["r001_q1"]
    correct_text = q.choices[q.correct_key]
    shuffled = shuffle_question(q, random.Random(7))
    assert shuffled.choices[shuffled.correct_key] == correct_text


def test_answer_positions_are_balanced_not_fixed(bank):
    assert answer_position_balance(bank.questions.values()) == {"A": 40, "B": 40, "C": 40, "D": 40}
    assert bank_balance_passes(bank.questions.values())


def test_session_shuffle_is_deterministic_and_varied(bank):
    questions = bank.get_questions("r006")
    one = shuffled_bundle(questions, "session-one")
    again = shuffled_bundle(questions, "session-one")
    other = shuffled_bundle(questions, "session-two")
    assert [q.correct_key for q in one] == [q.correct_key for q in again]
    assert [q.choices for q in one] != [q.choices for q in other]
