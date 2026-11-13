import copy
import csv
import json
from pathlib import Path

import pytest

from core.ales import HEADERS, ales_id, import_ales
from core.study_content import StudyCatalog
from core.study_store import StudyStore
from core.vocabulary import save_vocabulary
from core.vocabulary_check import UNKNOWN
from scripts.prepare_ales_passages import build

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ['reading', 'ALES glossary', 'All', 'All', True]


def csv_file(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    return path


@pytest.fixture
def catalog(tmp_path):
    rows = [[t['term'], t['sense_hints'][0], '', str(n + 1), '97']
            for p in build()['passages'] for n, t in enumerate(p['targets'])]
    rows.append(['шахтёр', 'miner', '', '', '110'])  # no contextual coverage yet
    ales = tmp_path / 'ales.json'
    save_vocabulary(import_ales(csv_file(tmp_path / 'source.csv', rows)), ales)
    course = tmp_path / 'course.json'
    save_vocabulary(dict(version=1, items=[]), course)
    return StudyCatalog(vocabulary_path=course, ales_path=ales)


@pytest.fixture
def env(tmp_path):
    clock = [1800000000.0]
    store = StudyStore(tmp_path / 'profiles.db', clock=lambda: clock[0])
    token = store.create_profile('ALES test', 'test-password')
    return store, token, clock


def answer(store, token, key, correct=4, guess=False):
    p = store.check_state(token, key)['current']
    return store.submit_check(token, key, p['nonce'],
        [t['meaning'] if n < correct else UNKNOWN for n, t in enumerate(p['targets'])],
        [guess] * len(p['targets']))


def test_import_preserves_distinct_senses_blanks_and_stable_ids(tmp_path):
    rows = [['отставка', 'resignation', '', '16', '103'], ['отставка', 'retirement', '', '96', '103'],
            ['потерпеть аварию', 'to have an accident', '', '', '97'],
            ['отставка', 'resignation', '46', '16', '103']]
    data = import_ales(csv_file(tmp_path / 'source.csv', rows))
    assert data['report']['source_rows'] == 4 and data['report']['unique_entries'] == 3
    assert len(data['items'][0]['sources']) == 2
    assert data['items'][2]['sources'][0]['ales_item'] is None
    assert all(s['unit'] is None for w in data['items'] for s in w['sources'])
    assert ales_id('ОТСТАВКА', 'resignation') == data['items'][0]['id']
    assert ales_id('отставка', 'retirement') != data['items'][0]['id']
    reverse = import_ales(csv_file(tmp_path / 'reversed.csv', list(reversed(rows))))
    assert {w['id'] for w in reverse['items']} == {w['id'] for w in data['items']}


@pytest.mark.parametrize('rows', [[], [['word', '', '', '', '97']], [['слово', 'word', '', 'unknown', '97']]])
def test_invalid_import_fails_without_partial_output(tmp_path, rows):
    with pytest.raises(ValueError):
        import_ales(csv_file(tmp_path / 'invalid.csv', rows))


def test_all_authored_targets_link_exactly_and_uncovered_words_remain_available(catalog):
    assert build() == json.loads((ROOT / 'data/study/ales/passages.json').read_text(encoding='utf-8'))
    assert len(catalog.eligible('reading', 'ALES glossary', context_only=False)) == 61
    assert len(catalog.eligible('reading', 'ALES glossary')) == 60
    assert not catalog.checks('reading', 'Course modules')
    pairs = catalog.checks(*FILTERS)
    assert len(pairs) == 15 and all(len(p['targets']) == 4 for p in pairs)
    ids = [t['word_id'] for p in pairs for t in p['targets']]
    assert len(set(ids)) == 60
    for p in pairs:
        for t in p['targets']:
            assert t['word_ids'] == [t['word_id']]
            assert t['prompt'] and t['evidence'] in p['text']
            assert len(set([t['meaning'], *t['distractors']])) == 4
            assert catalog.context(t['word_id'], 'reading')['id'].startswith('short_')


@pytest.mark.parametrize('correct,guess,stage', [(4, False, 2), (0, False, 1), (2, False, 1), (3, False, 1), (4, True, 1)])
def test_outcomes_remain_private_until_completion_and_feed_review(env, catalog, correct, guess, stage):
    from ui.vocabulary_check import report_html
    store, token, clock = env
    key = store.start_check(token, catalog, FILTERS, maximum=2)
    first = answer(store, token, key, correct, guess)
    assert first['current']['stage'] == stage
    assert store.word_evidence(token, 'reading') == {} and report_html(first) == ''
    finished = answer(store, token, key, correct, guess)
    assert finished['status'] == 'complete' and finished['evidence_published']
    evidence = store.word_evidence(token, 'reading')
    assert len(evidence) == 8
    assert sum(e['focus'] for e in evidence.values()) == (8 if guess else 2 * (4 - correct))
    assert store.word_evidence(token, 'listening') == {}
    assert store.states(token) == {}  # no automatic mastery certification
    report = report_html(finished)
    assert 'Correctly recognized without guessing' in report and 'Words to work on again' in report
    assert '53 glossary entries were not tested' in report
    assert '60 of 61 entries' in report
    if correct < 4 or guess:
        nonce = store.next_card(token, catalog, group='ALES glossary', focus_only=True)
        attempt = store.attempt(token, nonce)
        assert evidence[attempt['word_id']]['focus']
        store.reveal(token, nonce, 'my answer')
        store.rate(token, nonce, 'Good')
        assert (attempt['word_id'], 'reading') in store.states(token)


def test_full_bank_no_repeat_and_restart_export(env, catalog):
    store, token, clock = env
    key = store.start_check(token, catalog, FILTERS, maximum=15)
    seen = set()
    for _ in range(15):
        state = store.check_state(token, key)
        assert state['current']['id'] not in seen
        seen.add(state['current']['id'])
        clock[0] += 1
        state = answer(store, token, key)
    assert state['end_reason'] == 'planned_length'
    reopened = StudyStore(store.path, clock=lambda: clock[0])
    login = reopened.login('ALES test', 'test-password')
    assert len(reopened.word_evidence(login, 'reading')) == 60
    exported = reopened.export(login)
    assert len(exported['vocabulary_checks']) == 60
    assert 'password' not in json.dumps(exported) and 'token_hash' not in json.dumps(exported)


def test_retries_early_stop_sparse_bank_and_profile_isolation(env, catalog, monkeypatch):
    store, token, clock = env
    key = store.start_check(token, catalog, FILTERS, 2)
    p = store.check_state(token, key)['current']
    with pytest.raises(ValueError):
        store.submit_check(token, key, p['nonce'], [None] * 4, [False] * 4)
    with pytest.raises(ValueError):
        store.submit_check(token, key, p['nonce'], [UNKNOWN] * 4, ['false'] * 4)
    state = answer(store, token, key, 0)
    assert store.submit_check(token, key, p['nonce'], [], []) == state
    finished = store.cancel_check(token, key)
    assert len(store.word_evidence(token, 'reading')) == 4
    assert store.cancel_check(token, key) == finished
    stranger = store.create_profile('Other ALES', 'test-password')
    with pytest.raises(ValueError):
        store.check_state(stranger, key)
    assert store.word_evidence(stranger, 'reading') == {}
    one = copy.deepcopy(catalog.checks(*FILTERS)[:1])
    monkeypatch.setattr(catalog, 'checks', lambda *args: copy.deepcopy(one))
    for _ in range(2):
        key = store.start_check(token, catalog, FILTERS, 15)
        state = answer(store, token, key)
        assert state['end_reason'] == 'content_exhausted'
    assert store.word_evidence(token, 'reading')[one[0]['targets'][0]['word_id']]['contexts'] == 1


def test_replaced_ales_check_does_not_publish_partial_evidence(env, catalog):
    store, token, clock = env
    key = store.start_check(token, catalog, FILTERS, 2)
    answer(store, token, key, 0)
    new = store.start_check(token, catalog, FILTERS, 2)
    assert store.word_evidence(token, 'reading') == {}
    assert store.check_state(token, key)['status'] == 'cancelled'
    assert store.cancel_check(token, new)['completed'] == []


def test_uncovered_word_can_be_studied_without_inventing_passage_evidence(env, catalog):
    store, token, clock = env
    wid = ales_id('шахтёр', 'miner')
    nonce = store.next_card(token, catalog, group='ALES glossary', context_only=False,
                            exclude=[key for key in catalog.words if key != wid])
    assert store.attempt(token, nonce)['word_id'] == wid
    assert store.attempt(token, nonce)['context_id'] is None
    store.reveal(token, nonce, 'miner')
    store.rate(token, nonce, 'Good')
    assert (wid, 'reading') in store.states(token)
    assert wid not in store.word_evidence(token, 'reading')
    assert store.next_card(token, catalog, group='ALES glossary', skill='listening',
                           exclude=[key for key in catalog.words if key != wid]) is None


def test_late_completed_snapshot_does_not_overwrite_newer_check(env, catalog):
    store, token, clock = env
    old = store.start_check(token, catalog, FILTERS, 2)
    before = answer(store, token, old, 0)
    passage = before['completed'][0]
    second_login = store.login('ALES test', 'test-password')
    # Different logins can have active snapshots, but same-context evidence is ordered.
    candidates = copy.deepcopy(catalog)
    candidates.checks = lambda *args: [copy.deepcopy(passage)]
    clock[0] += 5
    new = store.start_check(second_login, candidates, FILTERS, 2)
    answer(store, second_login, new, 4)
    clock[0] += 5
    store.cancel_check(token, old)
    assert all(not store.word_evidence(token, 'reading')[t['word_id']]['focus'] for t in passage['targets'])


def test_audio_provenance_and_listening_flow(env, catalog):
    import gradio as gr
    from scripts.generate_study_audio import decode, fingerprint, select_batch
    from scripts.prepare_vocabulary_passages import build as build_course
    from ui.vocabulary_check import CheckUI
    records = json.loads((ROOT / 'data/study/ales/audio.json').read_text())['recordings']
    passages = select_batch(build()['passages'], 'ales')
    assert len(records) == len(passages) == 15
    assert all(p['id'].startswith('vocab_') for p in select_batch(build()['passages'] + build_course()['passages'], 'original'))
    for p in passages:
        r = records[p['id']]
        assert r['script_fingerprint'] == fingerprint(p)
        assert r['commercial_use'] and r['attribution_required'] is False
        assert r['model_status'] == 'generally_available'
        assert abs(decode(ROOT / r['path']) - r['duration_seconds']) < .1
    assert len(catalog.checks('listening', 'ALES glossary')) == 15
    store, token, clock = env
    with gr.Blocks():
        ui = CheckUI()
    key = store.start_check(token, catalog, ['listening', *FILTERS[1:]], 2)
    state = store.check_state(token, key)
    outputs = ui.present(state)
    assert state['current']['text'] not in outputs[4] and outputs[-2]['value'] == ''
    for n in range(6):
        assert outputs[6 + n * 3]['visible'] is (n < 4)
        assert outputs[7 + n * 3]['visible'] is (n < 4)
    answer(store, token, key)
    finished = answer(store, token, key, 0)
    assert 'Transcript:' in ui.present(finished)[-2]['value']
    assert len(store.word_evidence(token, 'listening')) == 8 and not store.word_evidence(token, 'reading')
    nonce = store.next_card(token, catalog, skill='listening', group='ALES glossary', focus_only=True)
    attempt = store.attempt(token, nonce)
    assert catalog.contexts[attempt['context_id']]['audio_path']
