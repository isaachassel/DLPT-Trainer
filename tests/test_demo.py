import time
import re
import shutil
import subprocess
from pathlib import Path
import pytest

from core.storage import LocalStorage
from core.session import SessionFlowError, submit_current_bundle, mark_listening_play
from ui import demo


@pytest.mark.parametrize('script', ['demo_audio_lifecycle.cjs', 'demo_timer_lifecycle.cjs'])
def test_browser_controller_lifecycle(script):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the browser controller lifecycle test')
    result = subprocess.run([node, '--test', str(Path(__file__).with_name(script))],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def local_demo(monkeypatch, tmp_path):
    monkeypatch.setattr(demo.cb, 'STORAGE', LocalStorage(tmp_path / 'sessions', tmp_path / 'history'))
    monkeypatch.setattr(demo.cb, 'EXPORT_DIR', tmp_path / 'exports')
    return demo


def finish_audio(result):
    state = result[0]
    prefix = f'{state.session_id}|{state.current_passage_id}|'
    for phase in ('start1', 'end1', 'start2', 'end2'):
        demo.audio_event(state, prefix + phase)


@pytest.mark.parametrize('language', ['Russian', 'Chinese'])
@pytest.mark.parametrize('skill', ['Reading', 'Listening'])
@pytest.mark.parametrize('pattern', ['strong', 'weak', 'mixed'])
@pytest.mark.parametrize('starting_level', ['1+', '2'])
def test_demo_completes_only_selected_skill_and_adapts(local_demo, language, skill, pattern, starting_level):
    from core.adaptive import initialize_ability
    from core.constants import ILR_LEVELS
    result = local_demo.start_demo(language, skill, starting_level)
    initial = result[0].ability_for(skill.lower())
    neutral = initialize_ability(skill.lower(), '1+', broad=True)
    assert initial.posterior_weights == neutral.posterior_weights
    assert initial.standard_error == neutral.standard_error
    assert initial.routing_ilr == starting_level
    assert result[0].start_level == starting_level
    assert result[0].adaptive_start_policy == 'selected'
    assert result[1]['passage']['target_ilr'] == starting_level
    seen, bands = [], []
    while result[0].status == 'active':
        state, bundle, nonce = result[:3]
        assert state.demo_mode and state.mode == 'simulation'
        assert state.selected_skills == [skill.lower()]
        assert state.active_skill == skill.lower()
        assert state.timer_mode == 'strict' and state.time_limit_seconds_per_skill == 1800
        assert state.content_source == 'bank_only' and not state.hints_enabled
        assert not result[-3].get('visible')  # no report while active
        assert result[-5]['visible']
        assert ('demo-reading' if skill == 'Reading' else 'demo-listening') in result[-5]['elem_classes']
        passage = bundle['passage']
        assert passage['id'] not in seen
        seen.append(passage['id'])
        bands.append(passage['target_ilr'])
        if passage['skill'] == 'listening':
            assert passage['passage_ru'] not in result[6].get('value', '')
            assert not result[-4]['interactive']
            finish_audio(result)
        answers = []
        for i, q in enumerate(bundle['questions']):
            correct = pattern == 'strong' or (pattern == 'mixed' and i % 2 == 0)
            answers.append(q['correct_key'] if correct else next(k for k in q['choices'] if k != q['correct_key']))
        result = local_demo.submit_demo(state, bundle, nonce, *(answers + [None] * (5-len(answers))))
        assert len(seen) < 30
    assert result[0].status == 'completed'
    assert len(result[0].responses) == 12
    assert {r.skill for r in result[0].responses} == {skill.lower()}
    assert result[-3]['visible']
    assert not result[-5]['visible']
    assert 'Around ILR' in result[-3]['value']
    assert 'Why the test ended:' in result[-3]['value']
    assert 'not an official DLPT score' in result[-3]['value']
    assert all(r.listening_play_count == 2 for r in result[0].responses if r.skill == 'listening')
    assert len(set(bands)) > 1
    end_route = result[0].ability_for(skill.lower()).routing_ilr
    if pattern == 'strong':
        assert ILR_LEVELS.index(end_route) > ILR_LEVELS.index(starting_level)
    elif pattern == 'weak':
        assert ILR_LEVELS.index(end_route) < ILR_LEVELS.index(starting_level)


def listening_result():
    return demo.start_demo('Russian', 'Listening')


def test_audio_requires_ordered_current_passage_events(local_demo):
    result = listening_result()
    state, data = result[:2]
    assert state.active_skill == 'listening'
    prefix = f'{state.session_id}|{state.current_passage_id}|'
    for event in ('wrong|passage|start1', prefix+'end2', prefix+'start2'):
        local_demo.audio_event(state, event)
    assert state.current_listening_plays == state.current_listening_completed == 0
    bundle = demo.cb._bundle_from_dict(data)
    answers = {q.id: q.correct_key for q in bundle.questions}
    for phase in ('start1', 'end1', 'start2'):
        local_demo.audio_event(state, prefix+phase)
        local_demo.audio_event(state, prefix+phase)  # duplicate ignored
        with pytest.raises(SessionFlowError, match='both complete'):
            submit_current_bundle(state, bundle.passage, bundle.questions, answers, result[2])
    confirmed = local_demo.audio_event(state, prefix+'end2')
    assert confirmed[1]['interactive']
    assert state.current_listening_plays == state.current_listening_completed == 2
    with pytest.raises(SessionFlowError):
        mark_listening_play(state)
    local_demo.audio_event(state, prefix+'end2')
    assert state.current_listening_completed == 2


def test_timer_does_not_restart_audio_and_expiry_advances(local_demo):
    result = listening_result()
    early = local_demo.expire_demo(*result[:3])
    assert early[7] == {'__type__': 'update'}
    result[0].skill_deadline_epoch = time.time() - 1
    ended = local_demo.expire_demo(*result[:3])
    assert ended[0].status == 'completed'
    assert not ended[7]['visible']
    assert 'time limit' in ended[-3]['value']
    assert 'Not enough answers' in ended[-3]['value']
    saved = local_demo.cb.STORAGE.load_checkpoint(ended[0].session_id)
    assert saved.assessment_end_reasons['listening'] == 'time_limit'


def test_missing_answer_keeps_completed_audio(local_demo):
    result = listening_result()
    finish_audio(result)
    failed = local_demo.submit_demo(*result[:3], *([None]*5))
    assert failed[0].current_listening_completed == 2
    assert failed[7] == {'__type__': 'update'}
    assert 'Answer every question' in failed[3]['value']


def test_demo_setup_has_no_workshop_or_mode_controls():
    app = demo.build_app()
    config = app.get_config_file()
    labels = [c['props'].get('label') for c in config['components']]
    assert 'Choose your language' in labels
    assert 'Choose your test' in labels
    selector = next(c for c in config['components'] if c['props'].get('label') == 'Choose your test')
    assert [choice[0] for choice in selector['props']['choices']] == ['Reading', 'Listening']
    start = next(c for c in config['components'] if c['props'].get('label') == 'Choose your starting difficulty')
    assert start['props']['value'] == '1+'
    assert [choice[1] for choice in start['props']['choices']] == ['1+', '2']
    assert not {'Mode', 'Skill selection', 'Content source', 'Training voice preference'} & set(labels)
    values = [str(c['props'].get('value', '')) for c in config['components']]
    assert not any('workshop' in v.lower() or 'bank backup' in v.lower() for v in values)


def test_setup_failure_is_visible_outside_hidden_test_panel(monkeypatch):
    import gradio as gr
    monkeypatch.setattr(demo.cb, 'start_session_callback',
                        lambda *a, **kw: [None, None, None, {'value': 'No approved passages available'}])
    with pytest.raises(gr.Error, match='No approved passages'):
        demo.start_demo('Russian')


@pytest.mark.parametrize('starting_level', ['1+', '2'])
def test_resume_preserves_demo_progress_and_completed_listens(local_demo, starting_level):
    from types import SimpleNamespace
    result = local_demo.start_demo('Russian', 'Listening', starting_level)
    finish_audio(result)
    state = result[0]
    restored = local_demo.restore_demo(SimpleNamespace(query_params={'resume': state.session_id}))
    assert restored[0].current_passage_id == state.current_passage_id
    assert restored[0].start_level == starting_level
    assert restored[0].adaptive_start_policy == 'selected'
    assert restored[0].listening_ability == state.listening_ability
    assert restored[0].skill_deadline_epoch == state.skill_deadline_epoch
    assert restored[0].current_listening_completed == 2
    assert 'Both listens complete' in restored[7]['value']
    assert '<audio' not in restored[7]['value']
    assert restored[-4]['interactive']
    assert len(local_demo.restore_demo(SimpleNamespace(query_params={}))) == len(restored)


def test_second_passage_resets_audio_and_rejects_prior_events(local_demo):
    result = listening_result()
    finish_audio(result)
    state, bundle, nonce = result[:3]
    previous = f'{state.session_id}|{state.current_passage_id}|'
    answers = [q['correct_key'] for q in bundle['questions']]
    advanced = local_demo.submit_demo(state, bundle, nonce, *(answers + [None]*(5-len(answers))))
    assert advanced[0].current_listening_plays == advanced[0].current_listening_completed == 0
    assert 'data-round="1"' in advanced[7]['value']
    for event in ('start1', 'end1', 'start2', 'end2'):
        local_demo.audio_event(advanced[0], previous+event)
    assert advanced[0].current_listening_plays == 0
    finish_audio(advanced)
    assert advanced[0].current_listening_completed == 2


@pytest.mark.parametrize('value', [None, '', '0', '3', 'Preparation', '<script>'])
def test_invalid_starting_difficulty_does_not_create_session(local_demo, value):
    import gradio as gr
    with pytest.raises(gr.Error, match='Choose Level'):
        local_demo.start_demo('Russian', 'Reading', value)
    assert not list(local_demo.cb.STORAGE.session_dir.glob('*.json'))


@pytest.mark.parametrize('starting_level', ['1+', '2'])
def test_missing_starting_band_stays_in_setup(local_demo, monkeypatch, starting_level):
    import gradio as gr
    from core.preset_bank import PresetBank
    original = local_demo.cb.PRESET_BANK
    bank = PresetBank(original.path, original.asset_root).load()
    bank.passages = {k: p for k, p in bank.passages.items() if p.target_ilr != starting_level}
    bank._reindex()
    monkeypatch.setattr(local_demo.cb, 'PRESET_BANK', bank)
    with pytest.raises(gr.Error, match=re.escape(f'No approved Level {starting_level} starting passage')):
        local_demo.start_demo('Russian', 'Reading', starting_level)
    assert not list(local_demo.cb.STORAGE.session_dir.glob('*.json'))


def test_full_app_simulation_and_older_demo_keep_medium_start(local_demo):
    from types import SimpleNamespace
    result = local_demo.cb.start_session_callback(
        demo.SIMULATION_MODE_LABEL, 'Reading', '1+', '2',
        'Shortened practice — 12 questions per skill / 30 minutes', 'Strict countdown',
        [], [], 'End of session', False, False, 'Automatic natural Russian voice', 'Normal', '', progress=None)
    state = result[0]
    assert state.adaptive_start_policy == 'medium'
    assert state.start_level == '1+'
    assert state.reading_ability.routing_ilr == '2'
    assert result[1]['passage']['target_ilr'] == '2'
    state.demo_mode = True
    local_demo.cb.STORAGE.save_checkpoint(state)
    restored = local_demo.restore_demo(SimpleNamespace(query_params={'resume': state.session_id}))
    assert restored[0].adaptive_start_policy == 'medium'
    assert restored[0].reading_ability == state.reading_ability
    assert restored[0].skill_deadline_epoch == state.skill_deadline_epoch
    assert restored[1]['passage']['id'] == state.current_passage_id
