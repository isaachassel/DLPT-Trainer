from __future__ import annotations

import gradio as gr

from ui.components import ANSWER_KEYS, answer_radio
from ui.callbacks import _blank_questions


def test_dynamic_answer_radio_accepts_b_even_if_server_choices_are_stale():
    radio = answer_radio(label="Question 1")
    # Reproduce the production failure: dynamic frontend labels can be present
    # while Gradio's server component still reports no choices.
    radio.choices = []
    assert radio.preprocess("B") == "B"


def test_dynamic_answer_radio_rejects_unknown_values():
    radio = answer_radio(label="Question 1")
    try:
        radio.preprocess("E")
    except gr.Error as exc:
        assert "A, B, C, or D" in str(exc)
    else:
        raise AssertionError("Unknown answer key was accepted")


def test_hidden_question_updates_do_not_clear_stable_answer_key_contract():
    updates = _blank_questions()
    radio_updates = updates[1::2]
    assert len(radio_updates) == 5
    for update in radio_updates:
        assert "choices" not in update
