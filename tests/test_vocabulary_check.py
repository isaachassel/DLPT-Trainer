import copy
import json
from pathlib import Path

import pytest

from core.study_content import StudyCatalog
from core.study_store import StudyStore, StudyError
from core.study_scheduler import mastery
from core.vocabulary import normalize_ru, save_vocabulary
from core.vocabulary_check import evidence_summary, UNKNOWN
from scripts.prepare_vocabulary_passages import build
from scripts.generate_study_audio import fingerprint, decode

FILTERS = ['reading', 'Course modules', 'All', 'All', True]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog(tmp_path):
    words = [dict(id=t['id'], russian=t['term'], english=t['sense_hints'][0], variants=[normalize_ru(t['term'])],
                  sources=[dict(group='Mod ' + str(p['stage']), lesson='1', row=n)])
             for p in build()['passages'] for n, t in enumerate(p['targets'])]
    path = tmp_path / 'vocabulary.json'
    save_vocabulary(dict(version=1, items=words), path)
    return StudyCatalog(vocabulary_path=path)


@pytest.fixture
def env(tmp_path):
    now = [1800000000.0]
    store = StudyStore(tmp_path / 'profiles.sqlite3', clock=lambda: now[0])
    token = store.create_profile('Learner', 'test-password')
    return store, token, now


def submit(store, token, identifier, correct=6, guessed=False):
    state = store.check_state(token, identifier)
    p = state['current']
    answers = [t['meaning'] if n < correct else t['distractors'][0] for n, t in enumerate(p['targets'])]
    return store.submit_check(token, identifier, p['nonce'], answers, [guessed] * len(answers))


def test_authored_passages_and_short_contexts_link_without_private_workbook(catalog):
    assert len(catalog.checks()) == 9
    assert all(len(p['targets']) == 6 for p in catalog.checks())
    assert len(catalog.eligible('listening')) == 54
    assert build() == json.loads((ROOT / 'data/study/passages.json').read_text(encoding='utf-8'))
    assert all('short_' + t['id'] in catalog.by_word[t['id']] for p in build()['passages'] for t in p['targets'])


def test_new_recordings_have_valid_provenance_and_decode():
    records = json.loads((ROOT / 'data/study/audio.json').read_text())['recordings']
    assert len(records) == 9
    for p in build()['passages']:
        r = records[p['id']]
        assert r['script_fingerprint'] == fingerprint(p)
        assert r['commercial_use'] and r['attribution_required'] is False
        assert r['model_status'] == 'generally_available' and r['account_tier'] == 'starter'
        assert abs(decode(ROOT / r['path']) - r['duration_seconds']) < .1
    assert sum(r['input_characters'] for r in records.values()) == 5208


@pytest.mark.parametrize('correct,stages', [(6, [1, 2, 3]), (0, [1, 1, 1]), (4, [1, 1, 1]), (5, [1, 2, 3])])
def test_strong_weak_mixed_and_borderline_routes(env, catalog, correct, stages):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    observed, ids = [], []
    for _ in range(3):
        state = store.check_state(token, identifier)
        observed.append(state['current']['stage'])
        ids.append(state['current']['id'])
        state = submit(store, token, identifier, correct)
    assert observed == stages and len(set(ids)) == 3
    assert state['status'] == 'complete' and state['end_reason'] == 'planned_length'
    assert len(store.word_evidence(token, 'reading')) == 18
    assert store.word_evidence(token, 'listening') == {}
    assert store.states(token) == {}  # A single check does not certify mastery.


def test_guessed_correct_answers_do_not_raise_difficulty(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    state = submit(store, token, identifier, 6, True)
    assert state['current']['stage'] == 1
    assert all(e['focus'] for e in store.word_evidence(token, 'reading').values())


def test_guess_adjustment_uncertainty_and_repeated_context_deduplication():
    observation = dict(source='passage1', correct=True, guessed=False, observed_at=1)
    first = evidence_summary([observation])
    repeated = evidence_summary([observation, {**observation, 'observed_at': 2}])
    assert first['mean'] == repeated['mean'] and repeated['contexts'] == 1
    assert first['high'] - first['low'] > .6
    guess = evidence_summary([{**observation, 'guessed': True}])
    assert .5 < guess['mean'] < first['mean']
    wrong = evidence_summary([{**observation, 'correct': False}])
    assert wrong['mean'] < .5 and wrong['focus']


def test_missing_answers_nonce_retries_and_profile_isolation(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    original = store.check_state(token, identifier)['current']
    with pytest.raises(ValueError, match='Answer every'):
        store.submit_check(token, identifier, original['nonce'], [None] * 6, [False] * 6)
    assert store.word_evidence(token, 'reading') == {}
    state = submit(store, token, identifier)
    retry = store.submit_check(token, identifier, original['nonce'], [], [])
    assert retry == state and len(retry['completed']) == 1
    with pytest.raises(ValueError, match='no longer active'):
        store.submit_check(token, identifier, 'forged-nonce', [UNKNOWN] * 6, [False] * 6)
    other = store.create_profile('Other', 'other-password')
    with pytest.raises(ValueError): store.check_state(other, identifier)
    assert not store.word_evidence(other, 'reading')


def test_failed_words_lead_to_new_context_reviews_and_success_resolves_focus(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS, maximum=2)
    state = submit(store, token, identifier, correct=5)
    wrong = state['completed'][0]['results'][-1]['word_id']
    store.cancel_check(token, identifier)
    nonce = store.next_card(token, catalog, focus_only=True)
    attempt = store.attempt(token, nonce)
    assert attempt['word_id'] == wrong and attempt['context_id'].startswith('short_')
    store.reveal(token, nonce, 'meaning')
    saved = store.rate(token, nonce, 'Good')
    assert mastery(saved) == 'Learning'
    assert store.next_card(token, catalog, focus_only=True) is None


def test_existing_known_word_missed_in_check_becomes_due_without_erasing_history(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    word = store.check_state(token, identifier)['current']['targets'][0]['word_id']
    nonce = store.next_card(token, catalog, exclude=[w for w in catalog.words if w != word])
    store.reveal(token, nonce, 'answer')
    before = store.rate(token, nonce, 'Easy')
    now[0] += 10
    submit(store, token, identifier, correct=0)
    after = store.states(token)[word, 'reading']
    assert after['due'] == now[0] and after['reviews'] == before['reviews']
    assert mastery(after) == 'Shaky'


def test_new_word_limit_still_applies_to_focus_and_due_reviews_win(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    submit(store, token, identifier, correct=0)
    store.set_new_limit(token, 0)
    assert store.next_card(token, catalog, focus_only=True) is None
    store.set_new_limit(token, 1)
    a = store.next_card(token, catalog, focus_only=True)
    store.reveal(token, a, '', unknown=True)
    store.rate(token, a, 'Again')
    assert store.next_card(token, catalog, focus_only=True) is None
    now[0] += 601
    assert store.next_card(token, catalog, focus_only=True)


def test_repeat_checks_same_passage_dont_manufacture_independent_evidence(env, catalog, monkeypatch):
    store, token, now = env
    one = catalog.checks()[:1]
    monkeypatch.setattr(catalog, 'checks', lambda *args: copy.deepcopy(one))
    for _ in range(3):
        identifier = store.start_check(token, catalog, FILTERS)
        state = submit(store, token, identifier)
        now[0] += 1
        assert state['end_reason'] == 'content_exhausted'
    assert len(store.word_evidence(token, 'reading')) == 6
    assert all(e['contexts'] == 1 for e in store.word_evidence(token, 'reading').values())


def test_cancel_empty_check_replacement_and_sparse_filters(env, catalog):
    from ui.vocabulary_check import report_html
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    state = store.cancel_check(token, identifier)
    assert 'No words assessed yet' in report_html(state)
    assert store.word_evidence(token, 'reading') == {}
    a = store.start_check(token, catalog, FILTERS)
    b = store.start_check(token, catalog, FILTERS)
    with pytest.raises(ValueError, match='replaced'): store.submit_check(token, a, 'any', [], [])
    with pytest.raises(ValueError, match='No passage check'):
        store.start_check(token, catalog, ['reading', 'Course modules', 'Absent', 'All', True])


def test_listening_hides_transcript_and_answers_until_report(env, catalog):
    import gradio as gr
    from ui.vocabulary_check import CheckUI
    store, token, now = env
    with gr.Blocks():
        ui = CheckUI()
    identifier = store.start_check(token, catalog, ['listening', *FILTERS[1:]], maximum=2)
    state = store.check_state(token, identifier)
    outputs = ui.present(state)
    assert state['current']['text'] not in outputs[4]
    assert outputs[-2]['value'] == '' and outputs[-1]['visible'] is False
    submit(store, token, identifier, correct=0)
    state = submit(store, token, identifier, correct=6)
    outputs = ui.present(state)
    assert 'Transcript:' in outputs[-2]['value'] and outputs[-1]['visible'] is True
    assert len(store.word_evidence(token, 'listening')) == 12
    assert store.word_evidence(token, 'reading') == {}


def test_evidence_survives_store_restart(env, catalog):
    store, token, now = env
    identifier = store.start_check(token, catalog, FILTERS)
    submit(store, token, identifier, correct=2)
    reopened = StudyStore(store.path, clock=lambda: now[0])
    second = reopened.login('Learner', 'test-password')
    assert reopened.word_evidence(second, 'reading') == store.word_evidence(token, 'reading')
    assert len(reopened.export(second)['vocabulary_checks']) == 6


def test_question_slots_hide_when_filtered_passage_shrinks(env, catalog, monkeypatch):
    import gradio as gr
    from ui.vocabulary_check import CheckUI
    store, token, now = env
    passages = copy.deepcopy(catalog.checks())[:2]
    passages[0]['targets'] = passages[0]['targets'][:3]
    passages[1]['targets'] = passages[1]['targets'][:2]
    passages[0]['stage'], passages[1]['stage'] = 1, 2
    monkeypatch.setattr(catalog, 'checks', lambda *args: copy.deepcopy(passages))
    with gr.Blocks():
        ui = CheckUI()
    identifier = store.start_check(token, catalog, FILTERS)
    for count in (3, 2):
        state = store.check_state(token, identifier)
        outputs = ui.present(state)
        assert len(outputs) == len(ui.outputs)
        assert f'· {count} words' in outputs[3]
        for n in range(6):
            slot, radio, guess = outputs[6 + n * 3:9 + n * 3]
            assert slot['visible'] is (n < count)
            assert len(radio['choices']) == (5 if n < count else 0)
            assert radio['value'] is None and guess['value'] is False
            assert radio['interactive'] is (n < count)
        if count == 3:
            submit(store, token, identifier, correct=3)
    finished = submit(store, token, identifier, correct=2)
    assert finished['end_reason'] == 'content_exhausted'
    assert len(store.word_evidence(token, 'reading')) == 5
    assert all(ui.present(finished)[6 + n * 3]['visible'] is False for n in range(6))
