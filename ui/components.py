from __future__ import annotations

from types import MethodType
from typing import Any

import gradio as gr


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
    """Return a native CheckboxGroup that also accepts a scalar payload.

    Some Gradio 6 browser/event combinations can submit a single selected value
    as a scalar string. The stock preprocessor iterates that string one character
    at a time. Patching only this component instance preserves Gradio's native
    frontend and API schema while safely wrapping the scalar in a one-item list.
    """

    component = gr.CheckboxGroup(*args, **kwargs)
    component.preprocess = MethodType(_scalar_tolerant_checkbox_preprocess, component)
    return component
