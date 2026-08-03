from __future__ import annotations
import importlib

from ui.callbacks import _passage_markdown, _test_render, start_session_callback
from core.constants import SIMULATION_MODE_LABEL
from core.models import PassageItem


def test_application_imports_in_pinned_style_environment():
    app = importlib.import_module("app")
    assert app.demo is not None


def test_application_builds_launch_configuration():
    app = importlib.import_module("app")
    config = app.demo.get_config_file()
    assert config.get("components") and config.get("dependencies")


def test_variable_question_bundles_render(bank):
    result = start_session_callback("Training Mode", "Reading", "1+", "2", "Short — 8 questions", "Off", [], [], "After each passage", False, True, "Starter-bank eSpeak voice", "Normal", "")
    bundle_data = result[1]
    visible_questions = len(bundle_data["questions"])
    assert 1 <= visible_questions <= 5


def test_strict_mode_does_not_expose_listening_transcript():
    result = start_session_callback(SIMULATION_MODE_LABEL, "Listening", "1+", "2", "Shortened practice — 12 questions per skill / 30 minutes", "Strict countdown", [], [], "End of session", False, True, "Starter-bank eSpeak voice", "Normal", "")
    state, bundle_data = result[0], result[1]
    from ui.callbacks import _bundle_from_dict
    bundle = _bundle_from_dict(bundle_data)
    rendered = _passage_markdown(bundle, state)
    assert bundle.passage.passage_ru not in rendered
    assert "transcript is hidden" in rendered.lower()
