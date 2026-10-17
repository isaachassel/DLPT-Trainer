from types import SimpleNamespace
from pathlib import Path

import gradio as gr
import pytest

from app import ROOT, launch_kwargs
from core.demo_hosting import is_hosted_demo
from scripts.package_demo import package_files
from ui import demo


def test_spaces_automatically_enables_hosted_safeguards(monkeypatch):
    monkeypatch.setenv('SPACE_ID', 'owner/demo')
    assert is_hosted_demo()
    settings = launch_kwargs()
    assert settings['allowed_paths'] == [str((ROOT / 'data/assessment/audio').resolve())]
    assert str(ROOT / 'storage') in settings['blocked_paths']
    assert str(ROOT / '.env') in settings['blocked_paths']


def test_hosted_resume_cannot_read_another_checkpoint(monkeypatch):
    monkeypatch.setenv('DEMO_HOSTED', 'true')
    def unexpected_read(*args):
        raise AssertionError('A hosted resume must not access disk')
    monkeypatch.setattr(demo.cb.STORAGE, 'load_checkpoint', unexpected_read)
    with pytest.raises(gr.Error, match='local demo'):
        demo.restore_demo(SimpleNamespace(query_params={'resume': 'known-session-code'}))
    assert len(demo.restore_demo(SimpleNamespace(query_params={}))) == 22


def test_local_preview_keeps_its_existing_behavior(monkeypatch):
    monkeypatch.delenv('SPACE_ID', raising=False)
    monkeypatch.delenv('DEMO_HOSTED', raising=False)
    assert not is_hosted_demo()
    assert 'blocked_paths' not in launch_kwargs()


def test_deployment_allowlist_excludes_private_local_data():
    names = {p.relative_to(ROOT).as_posix() for p in package_files()}
    assert {'app.py', 'core/demo_reporting.py', 'ui/demo_audio.js', 'data/assessment/bank.json'} <= names
    assert len([n for n in names if n.endswith('.mp3')]) == 38
    assert not any(n.startswith(('storage/', '.git/', '.venv/', 'tests/', 'data/pilots/')) for n in names)
    assert not any('.env' in n or '__pycache__' in n or n.endswith('.pyc') for n in names)


def test_packager_refuses_missing_input(tmp_path):
    with pytest.raises(ValueError, match='Missing or unsafe'):
        package_files(tmp_path)


def test_browser_upload_launcher_unpacks_paths_and_rejects_escape(tmp_path):
    import zipfile
    from scripts.launch_space import unpack
    archive = tmp_path / 'dlpt-demo.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('core/example.py', 'value = 1')
    root = unpack(archive)
    assert (root / 'core/example.py').read_text() == 'value = 1'
    assert unpack(archive) == root
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('../../outside.txt', 'must not extract')
    with pytest.raises(ValueError, match='Unsafe archive entry'):
        unpack(archive)
