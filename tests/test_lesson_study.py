import copy
import json
from types import SimpleNamespace

import pytest

from core.lesson_study import LessonCatalog, CATEGORIES, recommendation
from core.study_content import StudyCatalog
from core.study_store import StudyStore
from scripts.prepare_lesson_mappings import build_mappings
from ui.lesson_study import present, report_html, history_rows


@pytest.fixture
def catalog(tmp_path):
    # No private course import is needed to practice these passage questions.
    path = tmp_path / 'words.json'
    path.write_text(json.dumps({'version': 1, 'items': []}))
    return LessonCatalog(StudyCatalog(vocabulary_path=path))


@pytest.fixture
def store(tmp_path):
    return StudyStore(tmp_path / 'study.sqlite3')


def test_all_four_categories_reuse_verified_dialogues(catalog):
    for cat in CATEGORIES:
        reading, listening = catalog.choices(cat), catalog.choices(cat, 'listening')
        assert reading and len(reading) == len(listening)
        assert all(len(m['questions']) == 2 and m['audio_path'] for m in listening)
    assert len(catalog.choices('lexical')) == 17
    assert len(catalog.choices('structural', 'listening', 'Mod 6', 'Lesson 32')) == 2
    assert not catalog.choices('sociocultural', 'reading', 'Mod 6', 'Lesson 32')
    assert all(m['lesson'] is None for m in catalog.choices('sociocultural'))
    assert not catalog.choices('lexical', 'reading', 'Mod 6', 'Lesson 33')
    with pytest.raises(ValueError):
        catalog.choices('invented')


@pytest.mark.parametrize('correct,guess,label', [(0,False,'Prioritize this lesson'), (1,False,'Review this lesson'),
    (2,True,'Review to build confidence'), (2,False,'Looking good so far')])
def test_two_question_guidance_and_history(store, catalog, correct, guess, label):
    token = store.create_profile('Test', 'test-password')
    m = catalog.choices('structural')[0]
    state = store.start_lesson(token, catalog, m['id'], 'reading')
    answers = [q['answer'] if n < correct else q['distractors'][0] for n,q in enumerate(state['mapping']['questions'])]
    done = store.submit_lesson(token, state['id'], answers, [guess, False])
    assert recommendation(done['results']) == label
    assert label in report_html(done)
    assert len(history_rows(store, token, 'reading')) == 1
    assert history_rows(store, token, 'listening') == []
    assert store.states(token) == {} and store.word_evidence(token, 'reading') == {}


def test_incomplete_replaced_stale_and_cross_profile_submissions(store, catalog):
    token = store.create_profile('A', 'test-password')
    other = store.create_profile('B', 'test-password')
    m = catalog.choices()[0]
    old = store.start_lesson(token, catalog, m['id'], 'reading')
    s = store.start_lesson(token, catalog, m['id'], 'reading')
    with pytest.raises(ValueError, match='replaced'):
        store.submit_lesson(token, old['id'], ['I don’t know'] * 2, [False] * 2)
    with pytest.raises(ValueError, match='both'):
        store.submit_lesson(token, s['id'], [None, None], [False] * 2)
    with pytest.raises(ValueError, match='not available'):
        store.submit_lesson(other, s['id'], ['I don’t know'] * 2, [False] * 2)
    assert store.lesson_history(token) == []
    done = store.submit_lesson(token, s['id'], ['I don’t know'] * 2, [False] * 2)
    assert store.submit_lesson(token, s['id'], [], []) == done
    assert len(store.export(token)['lesson_checks']) == 1
    assert store.export(other)['lesson_checks'] == []


def test_repeated_passage_latest_history_preserves_attempts_and_snapshot(store, catalog):
    token = store.create_profile('A', 'test-password')
    m = catalog.choices('discourse')[0]
    original_answer = m['questions'][0]['answer']
    state = store.start_lesson(token, catalog, m['id'], 'listening')
    catalog.mappings[m['id']]['questions'][0]['answer'] = 'Edited after start'
    done = store.submit_lesson(token, state['id'], [original_answer, 'I don’t know'], [False] * 2)
    assert done['results'][0]['correct']
    catalog.mappings[m['id']]['questions'][0]['answer'] = original_answer
    second = store.start_lesson(token, catalog, m['id'], 'listening')
    store.submit_lesson(token, second['id'], ['I don’t know'] * 2, [False] * 2)
    assert len(store.lesson_history(token, 'listening')) == 1
    assert len(store.export(token)['lesson_checks']) == 2
    reopened = StudyStore(store.path)
    new_token = reopened.login('A', 'test-password')
    assert len(reopened.lesson_history(new_token)) == 1
    assert 'token' not in json.dumps(reopened.export(new_token))


def test_listening_withholds_transcript_and_explanations(store, catalog):
    token = store.create_profile('A', 'test-password')
    m = catalog.choices('sociocultural')[0]
    state = store.start_lesson(token, catalog, m['id'], 'listening')
    values = present(state)
    assert m['text'] not in str(values)
    assert all(q['explanation'] not in str(values) for q in m['questions'])
    assert values[-1]['visible'] is False and len(values[6]['choices']) == 5
    assert values[5]['visible'] and values[6]['visible']
    assert values[8]['visible'] and len(values[9]['choices']) == 5
    done = store.submit_lesson(token, state['id'], ['I don’t know'] * 2, [False] * 2)
    report = report_html(done)
    assert 'Prioritize this topic' in report and 'mapping pending' in report
    assert 'Transcript' in report


@pytest.mark.parametrize('mutation', ['category', 'lesson', 'evidence', 'choices', 'duplicate'])
def test_invalid_mapping_is_rejected(tmp_path, mutation):
    from scripts.prepare_vocabulary_passages import build
    source = build_mappings()
    m = source['mappings'][0]
    if mutation == 'category': m['category'] = 'unknown'
    if mutation == 'lesson': m['lesson_id'] = 'missing'
    if mutation == 'evidence': m['questions'][0]['evidence'] = 'not in this passage'
    if mutation == 'choices': m['questions'][0]['distractors'][0] = m['questions'][0]['answer']
    if mutation == 'duplicate': source['mappings'].append(copy.deepcopy(m))
    path = tmp_path / 'mapping.json'
    path.write_text(json.dumps(source), encoding='utf-8')
    passages = {p['id']: dict(p, text='\n\n'.join(t['text'] for t in p['turns']), audio_path=None) for p in build()['passages']}
    with pytest.raises(ValueError): LessonCatalog(SimpleNamespace(passages=passages), path)


def test_reproducible_mapping_file():
    from core.lesson_study import ROOT
    assert json.loads((ROOT / 'data/study/lesson_mappings.json').read_text(encoding='utf-8')) == build_mappings()
