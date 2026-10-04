from __future__ import annotations
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.item_bank import ItemBank


@pytest.fixture
def approved_bank(tmp_path, project_root):
    """Explicit test-only review decisions, never written into production content."""
    from core.preset_bank import PresetBank, Review, MANIFEST, read_package, write_package
    package = read_package(MANIFEST)
    for item in package.items:
        item.review = Review(status="approved", reviewer="TEST FIXTURE ONLY", reviewed_at="2026-10-03",
                             notes="Test fixture, not a linguistic review", reuse_attested=True)
    path = tmp_path / "approved-fixture.json"
    write_package(path, package)
    return PresetBank(path, project_root).load()


@pytest.fixture(scope="session")
def project_root():
    return ROOT


@pytest.fixture(scope="session")
def bank(project_root):
    return ItemBank([
        project_root / "tests/fixtures/legacy/starter_items.jsonl",
        project_root / "tests/fixtures/legacy/mandarin_starter_items.jsonl",
    ], writable_path=project_root / "storage/item_bank/generated_items.jsonl").load()
