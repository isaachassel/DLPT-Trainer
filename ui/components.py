from __future__ import annotations

from types import MethodType
from typing import Any

import gradio as gr


ANSWER_KEYS = ("A", "B", "C", "D")


def _scalar_tolerant_checkbox_preprocess(self: gr.CheckboxGroup, payload: Any):
    """Normalize a single CheckboxGroup value before Gradio validates it."""

    if payload is None:
        payload = []
    elif isinstance(payload, (str, int, float)):
        payload = [payload]
    elif isinstance(payload, tuple):
        payload = list(payload)
    return gr.CheckboxGroup.preprocess(self, payload)


def scalar_tolerant_checkbox_group(*args, **kwargs) -> gr.CheckboxGroup:
    """Return a native CheckboxGroup that also accepts a scalar payload."""

    component = gr.CheckboxGroup(*args, **kwargs)
    component.preprocess = MethodType(_scalar_tolerant_checkbox_preprocess, component)
    return component


def _answer_radio_preprocess(self: gr.Radio, payload: Any):
    """Accept only stable answer keys, independent of dynamic display labels.

    Gradio 6 validates Radio input against the choices stored on the server-side
    component instance. Our visible labels are updated passage-by-passage, while
    the stable values remain A/B/C/D. Some queued callbacks can otherwise see
    the original empty choices and reject a legitimate value such as ``B``.
    """

    if payload is None:
        return None
    value = str(payload).strip().upper()
    if value not in ANSWER_KEYS:
        raise gr.Error(f"Invalid answer key: {payload!r}. Choose A, B, C, or D.")
    return value


def answer_radio(*, label: str, visible: bool = False) -> gr.Radio:
    """Create a dynamically labelled answer radio with stable server values."""

    component = gr.Radio(
        choices=[(key, key) for key in ANSWER_KEYS],
        value=None,
        visible=visible,
        label=label,
    )
    component.preprocess = MethodType(_answer_radio_preprocess, component)
    return component
