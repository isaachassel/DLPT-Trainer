from __future__ import annotations

import pytest

from core.constants import QUESTION_TYPES
from ui.callbacks import TOPICS, start_session_callback
from ui.components import scalar_tolerant_checkbox_group


def test_checkbox_group_wraps_single_topic_string_before_validation():
    component = scalar_tolerant_checkbox_group(TOPICS)
    assert component.preprocess("Government and politics") == ["Government and politics"]


def test_checkbox_group_preserves_multi_value_payload():
    component = scalar_tolerant_checkbox_group(TOPICS)
    selected = ["Government and politics", "Culture and society"]
    assert component.preprocess(selected) == selected


def test_checkbox_group_still_rejects_unknown_values():
    component = scalar_tolerant_checkbox_group(TOPICS)
    with pytest.raises(Exception):
        component.preprocess("Not a real topic")


def test_start_session_normalizes_scalar_topic_and_competency():
    result = start_session_callback(
        "Training Mode",
        "Reading",
        "1+",
        "2",
        "Short — 8 questions",
        "Off",
        "Government and politics",
        "main idea",
        "After each passage",
        False,
        True,
        "Starter-bank eSpeak voice",
        "Normal",
        "",
    )
    state = result[0]
    assert state is not None
    assert state.topics == ["Government and politics"]
    assert state.competencies == ["main idea"]


def test_start_session_rejects_invalid_scalar_selection_without_crashing_callback():
    result = start_session_callback(
        "Training Mode",
        "Reading",
        "1+",
        "2",
        "Short — 8 questions",
        "Off",
        "G",
        QUESTION_TYPES[0],
        "After each passage",
        False,
        True,
        "Starter-bank eSpeak voice",
        "Normal",
        "",
    )
    assert result[0] is None
    assert "Invalid topic selection" in str(result[3])
