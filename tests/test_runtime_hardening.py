from __future__ import annotations

from pathlib import Path

from app import ROOT, launch_kwargs
from core.audio import controlled_audio_html, gradio_audio_url


def test_hugging_face_launch_explicitly_disables_ssr() -> None:
    kwargs = launch_kwargs()
    assert kwargs["ssr_mode"] is False


def test_only_audio_directories_are_exposed() -> None:
    kwargs = launch_kwargs()
    allowed = {Path(path).resolve() for path in kwargs["allowed_paths"]}
    assert (ROOT / "data" / "audio").resolve() in allowed
    assert (ROOT / "storage" / "exports").resolve() in allowed
    assert all(path.name in {"audio", "exports"} for path in allowed)
    assert ROOT.resolve() not in allowed


def test_audio_html_uses_gradio_file_route_not_base64(tmp_path: Path) -> None:
    audio = tmp_path / "sample clip.mp3"
    audio.write_bytes(b"x" * 1024)
    rendered = controlled_audio_html(str(audio), "sample", strict=True)
    assert "/gradio_api/file=" in rendered
    assert "sample%20clip.mp3" in rendered
    assert "data:audio" not in rendered
    assert "base64" not in rendered
    assert len(rendered) < 2000


def test_gradio_audio_url_is_absolute_and_encoded(tmp_path: Path) -> None:
    audio = tmp_path / "sample clip.mp3"
    expected_path = str(audio.resolve()).replace(" ", "%20")
    assert gradio_audio_url(audio) == f"/gradio_api/file={expected_path}"


def test_audio_component_registers_reactive_browser_handler() -> None:
    source = (ROOT / "ui" / "layout.py").read_text(encoding="utf-8")
    assert "watch('value', bindAudio)" in source
    assert "Press the play button in the player" in source
    assert "audio.controls = false" in source
    assert "audio.dataset.strict === 'true'" in source


def test_app_disables_hf_xet_before_importing_ui():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    disable_index = source.index('os.environ.setdefault("HF_HUB_DISABLE_XET", "1")')
    ui_import_index = source.index("from ui.layout import")
    assert disable_index < ui_import_index
    assert 'os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")' in source
