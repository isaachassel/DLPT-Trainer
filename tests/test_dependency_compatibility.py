from pathlib import Path

from packaging.version import Version

from scripts.check_space_dependencies import pinned_versions, validate

ROOT = Path(__file__).resolve().parents[1]


def test_space_dependency_pins_satisfy_gradio_extras() -> None:
    assert validate() == []


def test_pydantic_pin_matches_gradio_651_mcp_cap() -> None:
    pins = pinned_versions()
    assert pins["gradio"] == Version("6.5.1")
    assert pins["pydantic"] == Version("2.12.5")


def test_test_runner_is_not_installed_in_production_requirements() -> None:
    production = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    development = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest" not in production.lower()
    assert "pytest==9.0.2" in development
