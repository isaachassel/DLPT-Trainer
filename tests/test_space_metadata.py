from pathlib import Path

import yaml


def _front_matter() -> tuple[str, dict]:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    raw = readme.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    _, front_matter, _ = raw.split("---", 2)
    return front_matter, yaml.safe_load(front_matter)


def test_space_version_fields_are_quoted_strings() -> None:
    raw, metadata = _front_matter()
    assert 'python_version: "3.11"' in raw
    assert 'sdk_version: "6.5.1"' in raw
    assert metadata["python_version"] == "3.11"
    assert isinstance(metadata["python_version"], str)
    assert metadata["sdk_version"] == "6.5.1"
    assert isinstance(metadata["sdk_version"], str)


def test_space_uses_gradio_entrypoint() -> None:
    _, metadata = _front_matter()
    assert metadata["sdk"] == "gradio"
    assert metadata["app_file"] == "app.py"
