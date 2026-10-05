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
    assert (ROOT / "data" / "assessment" / "audio").resolve() in allowed
    assert (ROOT / "tests" / "fixtures" / "legacy" / "audio").resolve() not in allowed
    assert (ROOT / "data" / "audio").resolve() not in allowed
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
    from urllib.parse import unquote
    assert unquote(gradio_audio_url(audio)) == f"/gradio_api/file={audio.resolve()}"
    assert "%20" in gradio_audio_url(audio)


def test_audio_component_registers_reactive_browser_handler() -> None:
    source = (ROOT / "ui" / "layout.py").read_text(encoding="utf-8")
    assert "new MutationObserver(bindAudio)" in source
    assert "childList: true, subtree: true" in source
    assert "Press the play button in the player" in source
    assert "audio.controls = false" in source
    assert "audio.dataset.strict === 'true'" in source


def test_app_disables_hf_xet_before_importing_ui():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    disable_index = source.index('os.environ.setdefault("HF_HUB_DISABLE_XET", "1")')
    ui_import_index = source.index("from ui.demo import")
    assert disable_index < ui_import_index
    assert 'os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")' in source


def test_app_disables_gradio_and_hf_telemetry_before_importing_ui():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    ui_import_index = source.index("from ui.demo import")
    for setting in (
        'os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")',
        'os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")',
        'os.environ.setdefault("DO_NOT_TRACK", "1")',
    ):
        assert source.index(setting) < ui_import_index
    layout_source = (Path(__file__).resolve().parents[1] / "ui" / "layout.py").read_text(encoding="utf-8")
    assert "analytics_enabled=False" in layout_source


def test_submit_passage_uses_single_direct_queued_event() -> None:
    """Regression: do not reintroduce the silent prepare->then submit chain."""
    source = (Path(__file__).resolve().parents[1] / "ui" / "layout.py").read_text(encoding="utf-8")
    assert "submit_passage_stream_callback" in source
    assert "submit_prepare = submit_btn.click" not in source
    assert "submit_run = submit_prepare.then" not in source
    assert "outputs=[activity, *outputs]" in source


def test_submit_stream_first_yield_only_paints_busy_ui() -> None:
    from ui.callbacks import submit_passage_stream_callback

    stream = submit_passage_stream_callback(None, None, None, None, None, None, None, None, progress=None)
    first = next(stream)
    # activity + the 31 ordinary assessment render outputs
    assert len(first) == 32
    # The normal Submit Passage output is index 22, offset by one for activity.
    submit_update = first[23]
    assert submit_update.get("value") == "Submitting…"
    assert submit_update.get("interactive") is False
    # Session/bundle/nonce outputs are deliberately untouched during the busy repaint.
    assert first[1].get("__type__") == "update"
    assert first[1].get("value", object()) is not None or "value" not in first[1]
    second = next(stream)
    assert len(second) == 32
    try:
        next(stream)
    except StopIteration:
        pass
    else:
        raise AssertionError("submit stream should emit exactly busy + final renders")


def test_submit_stream_logs_entry_before_scoring_source_contract() -> None:
    source = (Path(__file__).resolve().parents[1] / "ui" / "callbacks.py").read_text(encoding="utf-8")
    function_start = source.index("def submit_passage_stream_callback")
    received = source.index("Submit passage event received", function_start)
    scoring = source.index("result = submit_passage_callback", function_start)
    assert received < scoring
