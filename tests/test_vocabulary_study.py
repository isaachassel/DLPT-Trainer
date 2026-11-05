import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape

import pytest

from core.vocabulary import import_workbook, save_vocabulary, normalize_ru, term_variants
from core.study_content import StudyCatalog
from core.study_scheduler import DAY, schedule, mastery, day_key
from core.study_store import StudyStore, StudyError


def workbook(path, rows, formulas=()):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="всё слова" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        cells = []
        for n, row in enumerate(rows, 1):
            cells.append(f'<row r="{n}">' + ''.join(
                f'<c r="{col}{n}" t="inlineStr">' + ('<f>UNTRUSTED()</f>' if (n, col) in formulas else '') +
                f'<is><t>{escape(value)}</t></is></c>' for col, value in zip('ABCD', row)) + '</row>')
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{ns}"><sheetData>{"".join(cells)}</sheetData></worksheet>')


def test_import_preserves_senses_and_sources_ignores_formulas(tmp_path):
    path = tmp_path / 'course.xlsx'
    workbook(path, [('Mod 1', '1', 'во́да', 'water'), ('Mod 2', '2', 'вода', 'water'),
                    ('Mod 2', '3', 'ключ', 'key'), ('Mod 2', '3', 'ключ', 'spring'),
                    ('Mod 3', '4', 'кот', 'cat'), ('Mod 3', '4', 'мир', '')], formulas={(5, 'D')})
    raw = import_workbook(path)
    assert raw['report']['source_rows'] == 4
    assert raw['report']['unique_entries'] == 3
    assert len(raw['items'][0]['sources']) == 2
    assert len(raw['report']['skipped']) == 2
    assert raw['items'][0]['variants'] == ['вода']
    assert raw['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert raw == import_workbook(path)


def test_normalization_preserves_short_i_and_separates_inflections():
    assert normalize_ru('ча́й / Ёж') == 'чай / еж'
    assert normalize_ru('и') != normalize_ru('й')
    assert term_variants('чита́ть / прочита́ть (чита́ю, чита́ешь)') == ['читать', 'прочитать']


@pytest.fixture
def catalog(tmp_path):
    words = [dict(id='a', russian='чай', english='tea', variants=['чай'],
                  sources=[dict(group='Mod 1', lesson='1', row=1)]),
             dict(id='b', russian='дом', english='house', variants=['дом'],
                  sources=[dict(group='Mod 1', lesson='2', row=2)]),
             dict(id='c', russian='мир', english='peace', variants=['мир'],
                  sources=[dict(group='Frequency', lesson='', row=3)])]
    vocabulary = tmp_path / 'vocabulary.json'
    save_vocabulary(dict(version=1, items=words), vocabulary)
    contexts = tmp_path / 'contexts.json'
    contexts.write_text(json.dumps([dict(id='ctx', term='чай', sense_hints=['tea'], target='чай',
                                        meaning='tea', text='Я пью чай.'),
                                   dict(id='ctx2', term='дом', sense_hints=['house'], target='дом',
                                        meaning='house', text='Это мой дом.')]), encoding='utf-8')
    bank = tmp_path / 'bank.json'
    bank.write_text('{"items":[]}', encoding='utf-8')
    return StudyCatalog(vocabulary, contexts, bank)


@pytest.fixture
def environment(tmp_path):
    clock = [1800000000.0]
    store = StudyStore(tmp_path / 'profiles.sqlite3', clock=lambda: clock[0])
    token = store.create_profile('Student', 'test password')
    return store, token, clock


def review(store, token, catalog, rating='Good', **kwargs):
    attempt = store.next_card(token, catalog, **kwargs)
    store.reveal(token, attempt, 'my answer')
    return attempt, store.rate(token, attempt, rating)


def test_context_coverage_and_filters_do_not_silently_supply_reading_audio(catalog):
    assert catalog.eligible() == ['a', 'b']
    assert catalog.eligible(lesson='2') == ['b']
    assert catalog.eligible('reading', 'All vocabulary', context_only=False) == ['a', 'b', 'c']
    assert catalog.eligible('listening', context_only=False) == []
    assert catalog.context('c', 'reading') is None


def test_scheduler_progress_lapse_and_uncertain_recall():
    now, state = 1800000000.0, None
    for expected in [1, 3, 7, 14, 30]:
        state = schedule(state, 'Good', now)
        assert state['interval_seconds'] == expected * DAY
        now = state['due']
    assert mastery(state) == 'Well known'
    hard = schedule(state, 'Hard', now)
    assert mastery(hard) == 'Shaky' and hard['due'] < now + 30 * DAY
    missed = schedule(state, 'Again', now)
    assert missed['due'] == now + 600 and missed['lapses'] == 1
    assert mastery(missed) == 'Shaky'
    assert schedule(None, 'Easy', now)['interval_seconds'] == 3 * DAY
    assert mastery(None) == 'New'


def test_repeat_success_same_day_does_not_establish_mastery():
    now, state = 1800000000.0, None
    for _ in range(9):
        state = schedule(state, 'Easy', now)
    assert state['streak'] == 1
    assert mastery(state) == 'Learning'


def test_local_day_accounts_for_timezone_and_dst():
    from datetime import datetime
    def ts(s): return datetime.fromisoformat(s).timestamp()
    assert day_key(ts('2026-11-01T06:30:00+00:00')) == '2026-10-31'
    assert day_key(ts('2026-11-01T08:30:00+00:00')) == '2026-11-01'
    assert day_key(ts('2026-11-01T09:30:00+00:00')) == '2026-11-01'
    assert day_key(ts('2026-11-01T06:30:00+00:00'), 'UTC') == '2026-11-01'


def test_profiles_are_isolated_persistent_and_hashed(environment, catalog):
    store, token, clock = environment
    review(store, token, catalog)
    other = store.create_profile('Other', 'other password')
    assert store.states(other) == {}
    reopened = StudyStore(store.path, clock=lambda: clock[0])
    restored = reopened.login('student', 'test password')
    assert reopened.states(restored) == store.states(token)
    with store.connect() as db:
        profile = db.execute('SELECT * FROM profiles WHERE name=?', ('Student',)).fetchone()
        assert profile['password_hash'] != 'test password' and len(profile['salt']) == 32
        assert token not in str([dict(r) for r in db.execute('SELECT * FROM sessions')])
    with pytest.raises(StudyError): store.login('Student', 'wrong password')
    with pytest.raises(StudyError): store.create_profile('STUDENT', 'test password')
    store.logout(token)
    with pytest.raises(StudyError): store.states(token)


def test_reveal_guard_unknown_rating_and_idempotency(environment, catalog):
    store, token, clock = environment
    attempt = store.next_card(token, catalog)
    with pytest.raises(StudyError, match='Reveal'): store.rate(token, attempt, 'Good')
    with pytest.raises(StudyError, match='guess'): store.reveal(token, attempt, '')
    store.reveal(token, attempt, '', unknown=True)
    with pytest.raises(StudyError, match='Again'): store.rate(token, attempt, 'Easy')
    first = store.rate(token, attempt, 'Again')
    assert store.rate(token, attempt, 'Again') == first
    assert len(store.export(token)['reviews']) == 1
    assert 'password' not in json.dumps(store.export(token))


def test_cross_session_stale_review_rejected_even_with_equal_clock(environment, catalog):
    store, token, clock = environment
    second = store.login('Student', 'test password')
    a = store.next_card(token, catalog)
    b = store.next_card(second, catalog)
    store.reveal(token, a, 'tea')
    store.reveal(second, b, 'tea')
    store.rate(token, a, 'Good')
    with pytest.raises(StudyError, match='another window'): store.rate(second, b, 'Easy')
    with pytest.raises(StudyError): store.attempt(second, a)


def test_daily_cap_due_priority_and_next_day(environment, catalog):
    store, token, clock = environment
    store.set_new_limit(token, 1)
    _, first = review(store, token, catalog, 'Again')
    assert store.next_card(token, catalog) is None
    clock[0] += 601
    a = store.next_card(token, catalog)
    assert store.attempt(token, a)['word_id'] == 'a'
    store.reveal(token, a, 'tea')
    store.rate(token, a, 'Good')
    clock[0] += DAY
    token = store.login('Student', 'test password')
    a = store.next_card(token, catalog)
    assert store.attempt(token, a)['word_id'] == 'a'  # due beats new
    store.reveal(token, a, 'tea')
    store.rate(token, a, 'Good')
    b = store.next_card(token, catalog)
    assert store.attempt(token, b)['word_id'] == 'b'  # new day allows new card


def test_skill_schedules_independent_and_daily_limit_shared(environment, catalog):
    store, token, clock = environment
    catalog.contexts['ctx']['audio_path'] = '/test/audio.mp3'
    review(store, token, catalog)
    review(store, token, catalog, skill='listening')
    states = store.states(token)
    assert ('a', 'reading') in states and ('a', 'listening') in states
    store.set_new_limit(token, 2)
    assert store.next_card(token, catalog) is None


def test_skip_finish_and_expired_session_do_not_record_progress(environment, catalog):
    store, token, clock = environment
    a = store.next_card(token, catalog)
    store.next_card(token, catalog, exclude=['a'])
    with pytest.raises(StudyError): store.reveal(token, a, 'tea')
    store.abandon(token)
    assert store.states(token) == {}
    clock[0] += 12 * 3600
    with pytest.raises(StudyError): store.states(token)


def test_zero_new_limit_and_empty_bank_are_explicit(environment, catalog):
    store, token, clock = environment
    store.set_new_limit(token, 0)
    assert store.next_card(token, catalog) is None
    assert store.next_card(token, catalog, lesson='absent') is None
    with pytest.raises(StudyError): store.set_new_limit(token, -1)
    with pytest.raises(StudyError): store.set_new_limit(token, 2.5)


def test_questions_hide_answers_and_listening_transcript_until_reveal(environment, catalog):
    from ui.study import StudyPresenter
    store, token, clock = environment
    catalog.contexts['ctx']['audio_path'] = '/test/audio.mp3'
    presenter = StudyPresenter(catalog, store)
    a = store.next_card(token, catalog, skill='listening')
    attempt, question, audio, answer = presenter.card(token, a)
    assert 'Я пью' not in question and 'tea' not in question and not answer
    assert audio == '/test/audio.mp3'
    store.reveal(token, a, '<script>guess</script>')
    _, _, _, answer = presenter.card(token, a)
    assert 'Я пью' in answer and 'tea' in answer
    assert '<script>' not in answer and '&lt;script&gt;' in answer


def test_local_launch_blocks_private_files_and_hosted_use(monkeypatch):
    import study_app
    options = study_app.launch_kwargs()
    assert options['server_name'] == '127.0.0.1' and options['share'] is False
    assert any(p.endswith('profiles.sqlite3') is False and p.endswith('study') for p in options['blocked_paths'])
    monkeypatch.setenv('SPACE_ID', 'someone/public-space')
    with pytest.raises(RuntimeError, match='local-only'): study_app.build_app()


def test_study_and_assessment_tabs_build_together(environment, catalog, monkeypatch):
    import study_app
    monkeypatch.delenv('SPACE_ID', raising=False)
    monkeypatch.delenv('DEMO_HOSTED', raising=False)
    app = study_app.build_app(catalog, environment[0])
    labels = [getattr(block, 'label', '') for block in app.blocks.values()]
    assert 'Vocabulary study' in labels and 'Adaptive assessment' in labels
    buttons = [getattr(block, 'value', '') for block in app.blocks.values() if block.__class__.__name__ == 'Button']
    assert 'Create profile' in buttons and 'Begin test' in buttons and 'Reveal meaning' in buttons


def test_original_context_builder_is_reproducible():
    from scripts.prepare_study_contexts import build
    root = Path(__file__).resolve().parents[1]
    assert build() == json.loads((root / 'data/study/contexts.json').read_text(encoding='utf-8'))


def test_real_audio_reuse_has_no_missing_targets_or_unreviewed_assets(tmp_path):
    from scripts.prepare_study_contexts import build
    # Independent of the user's private workbook: synthetic vocabulary from authored seeds.
    words = [dict(id=f'fixture{i}', russian=s['term'], english=s['sense_hints'][0],
                  variants=[normalize_ru(s['term'])], sources=[dict(group='Mod 1', lesson='1', row=i + 1)])
             for i, s in enumerate(build())]
    path = tmp_path / 'vocabulary.json'
    save_vocabulary(dict(version=1, items=words), path)
    catalog = StudyCatalog(vocabulary_path=path)
    assert len(catalog.contexts) == 162
    assert not catalog.unlinked_contexts
    audio_paths = {c['audio_path'] for c in catalog.contexts.values() if c['audio_path']}
    assert len(audio_paths) == 14
    assert all(Path(p).is_file() for p in audio_paths)
