import hashlib
import json

import pytest

from core.study_content import StudyCatalog
from core.study_store import StudyStore
from core.vocabulary import normalize_ru, save_vocabulary
from scripts.lesson32_study import build_lesson32
from scripts.prepare_vocabulary_passages import build
from scripts.generate_study_audio import select_batch, publish_records, BUDGET


@pytest.fixture
def lesson_catalog(tmp_path):
    words = [dict(id=t['id'], russian=t['term'], english=t['sense_hints'][0],
                  variants=[normalize_ru(t['term'])],
                  sources=[dict(group='Mod 6', lesson='Lesson 32', row=n)])
             for p in build_lesson32() for n, t in enumerate(p['targets'])]
    path = tmp_path / 'vocabulary.json'
    save_vocabulary(dict(version=1, items=words), path)
    return StudyCatalog(vocabulary_path=path)


def test_lesson32_links_all_senses_in_both_skills(lesson_catalog):
    for skill in ('reading', 'listening'):
        passages = lesson_catalog.checks(skill, 'Course modules', 'Mod 6', 'Lesson 32')
        assert len(passages) == 8
        assert {p['stage'] for p in passages} == {1, 2, 3}
        assert all(len(p['targets']) == 6 for p in passages)
        assert len({t['word_id'] for p in passages for t in p['targets']}) == 48
        assert not lesson_catalog.checks(skill, 'Course modules', 'Mod 6', 'Lesson 33')
    carrying = lesson_catalog.by_word['l32_movement_2']
    wearing = lesson_catalog.by_word['l32_movement_6']
    assert 'short_l32_movement_2' in carrying and 'short_l32_movement_6' not in carrying
    assert 'short_l32_movement_6' in wearing and 'short_l32_movement_2' not in wearing


@pytest.mark.parametrize('skill', ['reading', 'listening'])
def test_lesson32_misses_and_guesses_feed_separate_review_history(tmp_path, lesson_catalog, skill):
    store = StudyStore(tmp_path / 'profiles.sqlite3')
    token = store.create_profile('Lesson32 QA', 'test-password')
    identifier = store.start_check(token, lesson_catalog, [skill, 'Course modules', 'Mod 6', 'Lesson 32', True], 2)
    visited = []
    for _ in range(2):
        state = store.check_state(token, identifier)
        p = state['current']
        visited.append(p['id'])
        choices = [t['meaning'] if n != 0 else t['distractors'][0] for n, t in enumerate(p['targets'])]
        state = store.submit_check(token, identifier, p['nonce'], choices, [False, True, False, False, False, False])
    assert state['status'] == 'complete' and len(set(visited)) == 2
    evidence = store.word_evidence(token, skill)
    assert len(evidence) == 12 and sum(e['focus'] for e in evidence.values()) == 4
    assert store.word_evidence(token, 'listening' if skill == 'reading' else 'reading') == {}
    assert all(lesson_catalog.context(wid, skill) for wid, e in evidence.items() if e['focus'])


def test_generation_batches_are_disjoint_and_bounded():
    all_passages = build()['passages']
    old = select_batch(all_passages, 'original')
    new = select_batch(all_passages, 'lesson32')
    assert len(old) == 9 and len(new) == 8
    assert not {p['id'] for p in old} & {p['id'] for p in new}
    assert sum(len(t['text']) for p in new for t in p['turns']) <= BUDGET
    with pytest.raises(ValueError):
        select_batch([], 'lesson32')


def test_audio_publish_preserves_previous_batches_and_refuses_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.generate_study_audio.decode', lambda p: 10.0)
    stage = tmp_path / 'staged'
    stage.mkdir()
    (stage / 'new.mp3').write_bytes(b'fake mp3')
    folder = tmp_path / 'data/study'
    folder.mkdir(parents=True)
    manifest = folder / 'audio.json'
    old = {'version': 1, 'recordings': {'old': {'sha256': 'unchanged'}}}
    manifest.write_text(json.dumps(old))
    record = {'path': 'data/study/audio/new.mp3', 'sha256': hashlib.sha256(b'fake mp3').hexdigest()}
    publish_records(stage, {'new': record}, tmp_path)
    published = manifest.read_bytes()
    assert json.loads(published)['recordings']['old'] == old['recordings']['old']
    assert (folder / 'audio/new.mp3').read_bytes() == b'fake mp3'
    (stage / 'new.mp3').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='checksum'):
        publish_records(stage, {'new': record}, tmp_path)
    assert manifest.read_bytes() == published
    assert (folder / 'audio/new.mp3').read_bytes() == b'fake mp3'
