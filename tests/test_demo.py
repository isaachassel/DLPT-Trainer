import time
import pytest

from core.storage import LocalStorage
from core.session import SessionFlowError, submit_current_bundle, mark_listening_play
from ui import demo


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
@pytest.mark.parametrize('pattern', ['strong', 'weak', 'mixed'])
def test_demo_completes_both_sections_and_adapts(local_demo, language, pattern):
    result = local_demo.start_demo(language)
    seen, bands = [], []
    while result[0].status == 'active':
        state, bundle, nonce = result[:3]
        assert state.demo_mode and state.mode == 'simulation'
        assert state.selected_skills == ['reading', 'listening']
        assert state.timer_mode == 'strict' and state.time_limit_seconds_per_skill == 1800
        assert state.content_source == 'bank_only' and not state.hints_enabled
        assert not result[-3].get('visible')  # no report while active
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
    assert len(result[0].responses) == 24
    assert result[-3]['visible']
    assert all(r.listening_play_count == 2 for r in result[0].responses if r.skill == 'listening')
    assert len(set(bands)) > 1


def listening_result():
    result = demo.start_demo('Russian')
    result[0].skill_deadline_epoch = time.time() - 1
    return demo.expire_demo(*result[:3])


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
    assert not {'Mode', 'Skill selection', 'Content source', 'Training voice preference'} & set(labels)
    values = [str(c['props'].get('value', '')) for c in config['components']]
    assert not any('workshop' in v.lower() or 'bank backup' in v.lower() for v in values)
