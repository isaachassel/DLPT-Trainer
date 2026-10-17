"""Release checks: paid provenance, exact assets, and unchanged assessment content."""
import json
import hashlib
from pathlib import Path

import pytest

from core.preset_bank import MANIFEST, ROOT, read_package, validate_item
from scripts.package_demo import package_files


def test_active_audio_is_paid_reviewed_and_has_no_retired_assets():
    items = [i for i in read_package(MANIFEST).items if i.audio]
    assert len(items) == 38
    paths = {ROOT / i.audio.path for i in items}
    assert paths == set((ROOT / 'data/assessment/audio').glob('*.mp3'))
    for item in items:
        assert item.recording.account_tier == 'starter'
        review = item.recording.license_review.model_dump()
        assert review['commercial_use'] is True
        assert review['attribution_required'] is False
        assert review['model_status'] == 'generally_available'
        assert review['audio_sha256'] == item.audio_sha256
        validate_item(item, ROOT)


@pytest.fixture
def release_root(tmp_path):
    for name in ['app.py', 'requirements.txt', 'LICENSE', 'data/assessment/audio/NOTICE.md',
                 'data/assessment/audio_license_audit.json',
                 'data/assessment/audio/current.mp3', 'data/assessment/audio/retired.mp3']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture', encoding='utf-8')
    manifest = {'items': [{'id': 'fixture', 'recording': {'account_tier': 'starter',
        'license_review': {'commercial_use': True,
            'attribution_required': False, 'model_status': 'generally_available'}},
        'audio': {'path': 'data/assessment/audio/current.mp3'}}]}
    digest = hashlib.sha256(b'fixture').hexdigest()
    manifest['items'][0]['audio_sha256'] = digest
    manifest['items'][0]['recording']['license_review']['audio_sha256'] = digest
    path = tmp_path / 'data/assessment/bank.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return tmp_path, path, manifest


def test_deployment_excludes_retired_audio(release_root):
    root, _, _ = release_root
    files = {p.name for p in package_files(root)}
    assert 'current.mp3' in files
    assert 'retired.mp3' not in files


@pytest.mark.parametrize('change', ['free', 'missing_review', 'beta', 'attribution', 'escape', 'stale_hash'])
def test_deployment_rejects_unlicensed_or_unsafe_audio(release_root, change):
    root, path, manifest = release_root
    item = manifest['items'][0]
    review = item['recording']['license_review']
    if change == 'free':
        item['recording']['account_tier'] = 'free'
    elif change == 'missing_review':
        item['recording']['license_review'] = None
    elif change == 'beta':
        review['model_status'] = 'beta'
    elif change == 'attribution':
        review['attribution_required'] = True
    elif change == 'escape':
        item['audio']['path'] = '../../outside.mp3'
    else:
        (root / item['audio']['path']).write_bytes(b'different recording')
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        package_files(root)
