import json
from pathlib import Path
import time

import pytest

from core.adaptive import initialize_ability
from core.item_bank import ItemBank, shuffled_bundle
from core.models import SessionState, UserHistory
from core.preset_bank import ROOT, PresetBank, read_package
from core.reading_import import convert_reading_pack
from core.session import activate_bundle, select_next_bundle, submit_current_bundle, update_history
from core.source_credits import assessment_credits
from scripts.curate_assessment import promote
from scripts.import_reading_pack import import_file

PACK = ROOT / 'data/content_packs/ru-authentic-reading-pilot-01'


@pytest.fixture
def original():
    return json.loads((PACK / 'versions/v1/reading_bank.json').read_text(encoding='utf-8'))


def session(mode='assessment'):
    return SessionState(mode=mode, language='ru', selected_skills=['reading'],
        session_started_at_epoch=time.time(), reading_ability=initialize_ability('reading'),
        listening_ability=initialize_ability('listening'), start_level='1+', target_level='2')


def test_lossless_mapping_and_draft_isolation(original):
    package = convert_reading_pack(original)
    assert len(package.items) == 6
    assert sum(len(i.questions) for i in package.items) == 18
    assert package == read_package(PACK / 'package.json')
    for raw, item in zip(original['passages'], package.items):
        assert item.authoring_record == raw
        assert item.passage.passage_ru == raw['text']
        assert item.passage.family_id == raw['family_id']
        assert item.passage.calibrated_difficulty is None
        assert item.review.status == 'draft'
        assert raw['source']['title'] not in item.passage.orientation_en
        assert all(q.calibrated_difficulty is None for q in item.questions)
    drafts = PresetBank(PACK / 'package.json').load()
    assert drafts.pending_count == 6 and not drafts.passages
    production = PresetBank().load()
    assert production.passages and not set(drafts.reviewed_items) & set(production.passages)
    assert not {x.id for x in package.items} & set(production.passages)


@pytest.mark.parametrize('corruption', ['duplicate_id', 'duplicate_choice', 'invalid_key', 'quote',
                                      'paragraph', 'license', 'text', 'approved', 'skill'])
def test_import_rejects_bad_data(original, corruption):
    p = original['passages'][0]
    q = p['questions'][0]
    if corruption == 'duplicate_id': p['questions'][1]['id'] = q['id']
    elif corruption == 'duplicate_choice': q['options'][1]['text_en'] = q['options'][0]['text_en']
    elif corruption == 'invalid_key': q['correct_option_id'] = 'E'
    elif corruption == 'quote': q['evidence'][0]['quote_ru'] = 'not in the source'
    elif corruption == 'paragraph': q['evidence'][0]['paragraph_id'] = 'missing'
    elif corruption == 'license': p['source']['license_url'] = 'javascript:alert(1)'
    elif corruption == 'text': p['text'] = p['text'].replace('12', '13')
    elif corruption == 'approved': p['diagnostic_eligible'] = True
    elif corruption == 'skill': p['modality'] = 'listening'
    with pytest.raises((ValueError, KeyError)):
        convert_reading_pack(original)


def test_idempotence_and_version_history(tmp_path, original):
    src, out = tmp_path / 'input.json', tmp_path / 'draft/package.json'
    src.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')
    import_file(src, out)
    before = out.read_bytes()
    import_file(src, out)
    assert out.read_bytes() == before
    original['passages'][0]['questions'][0]['explanation_en'] += ' Reviewed wording.'
    src.write_text(json.dumps(original), encoding='utf-8')
    with pytest.raises(ValueError, match='increase --version'):
        import_file(src, out)
    import_file(src, out, 2)
    assert (out.parent / 'versions/v1/package.json').read_bytes() == before
    assert read_package(out).items[0].content_version == 2


def test_approval_is_explicit_and_previous_revision_survives(tmp_path):
    manifest = tmp_path / 'bank.json'
    pid = read_package(PACK / 'package.json').items[0].id
    with pytest.raises(ValueError, match='attestation'):
        promote(PACK / 'package.json', pid, 'Teacher', 'Reviewed', False, manifest, tmp_path)
    promote(PACK / 'package.json', pid, 'Teacher fixture', 'All rubric checks passed in fixture', True, manifest, tmp_path)
    bank = PresetBank(manifest, tmp_path).load()
    assert len(bank.passages) == 1
    assert bank.reviewed_items[pid].authoring_record['source']['license'] == 'CC BY 4.0'
    old = manifest.read_bytes()
    promote(PACK / 'package.json', pid, 'Teacher fixture', 'Withdraw pending edit', False, manifest, tmp_path, reject=True)
    archived = next((tmp_path / 'data/assessment/revisions').glob('*.json'))
    assert archived.read_bytes() == old


def native_bank(items):
    bank = ItemBank(Path('unused'))
    bank.passages = {i.passage.id: i.passage for i in items}
    bank.questions = {q.id: q for i in items for q in i.questions}
    bank._reindex()
    bank._loaded = True
    return bank


def test_family_exposure_includes_unanswered_and_changed_versions():
    item = read_package(PACK / 'package.json').items[0]
    state = session()
    activate_bundle(state, item.passage, item.questions)
    history = update_history(UserHistory(profile_id='preview-reader'), state)
    assert not history.response_records
    assert history.seen_family_ids == [item.passage.family_id]
    # Another version can have another passage ID and different text; same family excludes it.
    replacement = item.model_copy(deep=True)
    replacement.passage.id = 'different-version'
    replacement.passage.passage_ru += '\nAnother version'
    for q in replacement.questions: q.passage_id = replacement.passage.id
    bank = native_bank([replacement])
    for mode in ['assessment', 'simulation', 'diagnostic']:
        with pytest.raises(LookupError):
            select_next_bundle(session(mode), bank, history)


def test_shuffle_option_ids_and_complete_testlet_preserved():
    item = read_package(PACK / 'package.json').items[0]
    state = session('simulation')
    state.max_questions_per_skill = 2
    bundle = activate_bundle(state, item.passage, shuffled_bundle(item.questions, 'a-stable-test'))
    assert len(bundle.questions) == 3
    records = submit_current_bundle(state, item.passage, bundle.questions,
                                    {q.id: q.correct_key for q in bundle.questions}, 'fixture-submit')
    for original, record in zip(item.questions, records):
        assert record.is_correct
        assert record.option_id_map[record.selected_key] == original.correct_key
    from core.demo_reporting import demo_end_reason
    assert demo_end_reason(state, 'reading') == 'All 3 questions were completed.'


def test_post_assessment_attribution_is_snapshot_only_and_safe():
    item = read_package(PACK / 'package.json').items[0]
    state = session()
    activate_bundle(state, item.passage, item.questions)
    assert assessment_credits(state) == ''
    state.status = 'stopped'
    html = assessment_credits(state)
    assert item.passage.provenance['source_title'] in html
    for field in ['source_original_url', 'source_archive_revision_url', 'source_license_url', 'publication_date']:
        assert item.passage.provenance[field].replace('&', '&amp;') in html
    assert 'CC BY 4.0' in html and 'Whitespace normalized' in html
    credit = state.source_credits[item.id]
    credit['source_title'] = '<script>bad</script>'
    credit['source_original_url'] = 'javascript:alert(1)'
    html = assessment_credits(state)
    assert '<script>' not in html and 'javascript:' not in html


def test_uncredentialed_approved_fixture_flow(monkeypatch, tmp_path):
    from ui import demo
    from core.storage import LocalStorage
    from scripts.preview_reading_pack import preview_score
    manifest = tmp_path / 'bank.json'
    for item in read_package(PACK / 'package.json').items:
        promote(PACK / 'package.json', item.id, 'Test fixture only', 'Fixture approval', True, manifest, tmp_path)
    bank = PresetBank(manifest, tmp_path).load()
    monkeypatch.setattr(demo.cb, 'PRESET_BANK', bank)
    monkeypatch.setattr(demo.cb, 'STORAGE', LocalStorage(tmp_path / 'sessions', tmp_path / 'history'))
    monkeypatch.setattr(demo.cb, 'EXPORT_DIR', tmp_path / 'exports')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '1')
    for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ELEVENLABS_API_KEY', 'HF_TOKEN']:
        monkeypatch.delenv(key, raising=False)
    result = demo.start_demo('Russian', 'Reading')
    assert result[0] is not None
    for _ in range(8):
        if result[0].status != 'active': break
        state, bundle, nonce = result[:3]
        source = bank.passages[bundle['passage']['id']]
        visible = json.dumps(result[3:], ensure_ascii=False)
        assert source.provenance['source_title'] not in visible
        assert source.provenance['publication_date'] in visible
        assert bundle['questions'][0]['rationale_en'] not in visible
        answers = [q['correct_key'] for q in bundle['questions']]
        result = demo.submit_demo(state, bundle, nonce, *answers, *([None] * (5-len(answers))))
    assert result[0].status != 'active'
    assert 'Sources for your reading' in result[-3]['value']
    assert result[0].source_credits
    # Browser family memory carries into a new test and cannot recycle the bank.
    remaining = list(bank.passages.values())
    with pytest.raises(Exception, match='unavailable'):
        demo.start_demo('Russian', 'Reading', '1+', [p.family_id for p in remaining])
    item = read_package(PACK / 'package.json').items[0]
    report = preview_score(item, [q.correct_key for q in item.questions])
    assert '3 of 3' in report and 'No proficiency level' in report
    assert 'Around ILR' not in report


def test_drafts_and_original_authoring_files_excluded_from_deployment():
    from scripts.package_demo import package_files
    names = [p.relative_to(ROOT).as_posix() for p in package_files()]
    assert not any(p.startswith('data/content_packs/') for p in names)
    assert not any('preview_reading' in p for p in names)
