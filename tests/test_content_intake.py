import json
from pathlib import Path

import pytest

from core.content_intake import IntakePackage, convert_package
from core.preset_bank import PresetBank, read_package
from scripts import import_contributor

EXAMPLE = Path(__file__).resolve().parents[1] / 'docs/contributor-kit/contributor.example.json'


def test_examples_convert_to_pending_drafts_without_changing_text():
    source = IntakePackage.model_validate_json(EXAMPLE.read_text(encoding='utf-8'))
    drafts, findings = convert_package(source)
    assert {i.passage.language for i in drafts.items} == {'ru', 'zh-CN'}
    for original, item in zip(source.items, drafts.items):
        assert item.passage.passage_ru == original.text
        assert item.passage.provenance['source_locator'] == original.source.locator
        assert item.review.status == 'draft' and not item.review.reuse_attested
        assert item.passage.validation_status == 'needs_review'
        assert item.audio is None
        assert [q.correct_key for q in item.questions] == [q.correct_key for q in original.questions]
    assert any('Recording' in str(f) for f in findings)


@pytest.mark.parametrize('kind', ['duplicate_id', 'wrong_choices', 'secret', 'audio_escape', 'unknown_level'])
def test_invalid_import_is_rejected(kind):
    data = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    if kind == 'duplicate_id':
        data['items'].append(data['items'][0])
    elif kind == 'wrong_choices':
        data['items'][0]['questions'][0]['choices'].pop('D')
    elif kind == 'secret':
        data['items'][0]['source']['api_key'] = 'not-a-real-secret'
    elif kind == 'audio_escape':
        data['items'][-1]['audio_file'] = 'audio/../../private.mp3'
    else:
        data['items'][0]['target_ilr'] = 'unknown'
    with pytest.raises(ValueError):
        convert_package(IntakePackage.model_validate(data))


def test_bad_evidence_reported_without_rewriting_source():
    source = IntakePackage.model_validate_json(EXAMPLE.read_text(encoding='utf-8'))
    source.items[0].questions[0].evidence = 'Missing evidence phrase'
    drafts, findings = convert_package(source)
    assert 'evidence_in_passage' in findings[0]['checks_to_review']
    assert drafts.items[0].questions[0].evidence_ru == 'Missing evidence phrase'


def test_cli_only_writes_new_workshop_drafts(tmp_path, monkeypatch):
    monkeypatch.setattr(import_contributor, 'ROOT', tmp_path)
    output = tmp_path / 'storage/workshop/intake'
    count = import_contributor.import_file(EXAMPLE, output)
    assert len(read_package(output / 'package.json').items) == count
    bank = PresetBank(output / 'package.json', output).load()
    assert not bank.passages and bank.pending_count == count
    with pytest.raises(FileExistsError):
        import_contributor.import_file(EXAMPLE, output)
    with pytest.raises(ValueError, match='workshop'):
        import_contributor.import_file(EXAMPLE, tmp_path / 'data/assessment')
