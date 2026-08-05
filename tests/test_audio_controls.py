from __future__ import annotations
import os
import time
from pathlib import Path

from core.audio import cleanup_audio_files, controlled_audio_html, resolve_audio_path, validate_audio_file


def test_temporary_audio_cleanup_works(tmp_path):
    old = tmp_path / "old.mp3"
    old.write_bytes(b"x" * 1000)
    os.utime(old, (time.time()-10000, time.time()-10000))
    new = tmp_path / "new.mp3"
    new.write_bytes(b"x" * 1000)
    removed = cleanup_audio_files([tmp_path], max_age_seconds=5000)
    assert old in removed and new.exists()


def test_referenced_audio_is_not_cleaned(tmp_path):
    old = tmp_path / "keep.mp3"
    old.write_bytes(b"x" * 1000)
    os.utime(old, (time.time()-10000, time.time()-10000))
    removed = cleanup_audio_files([tmp_path], 5000, {str(old)})
    assert old.exists() and old not in removed


def test_starter_audio_exists_and_is_nonempty(bank, project_root):
    asset = next(iter(bank.audio_assets.values()))
    path = resolve_audio_path(asset, project_root)
    assert validate_audio_file(path)


def test_strict_audio_html_exposes_initial_play_control(bank, project_root):
    asset = next(iter(bank.audio_assets.values()))
    path = resolve_audio_path(asset, project_root)
    rendered = controlled_audio_html(str(path), "x", strict=True)
    assert " controls" in rendered
    assert "autoplay" not in rendered
    assert "data:audio" not in rendered
    assert "Replay is disabled" in rendered


def test_controlled_audio_exposes_first_play_control(tmp_path: Path) -> None:
    path = tmp_path / "sample.mp3"
    path.write_bytes(b"x" * 1024)
    rendered = controlled_audio_html(str(path), "first-play", strict=True)
    assert " controls" in rendered
    assert "autoplay" not in rendered
    assert 'preload="metadata"' in rendered
    assert "Press the play button" in rendered
