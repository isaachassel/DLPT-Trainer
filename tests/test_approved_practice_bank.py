import json

from core.preset_bank import MANIFEST, PracticeBank, PresetBank, read_package


def test_all_bundled_content_is_new_method_and_shared_with_training(tmp_path):
    preset = PresetBank().load()
    practice = PracticeBank(tmp_path / 'overlay.jsonl').load()
    assert len(preset.passages) == 66 and len(preset.questions) == 156
    assert preset.pending_count == 0
    assert set(practice.passages) == set(preset.passages)
    assert all(pid.startswith(('ru_pilot_', 'ru_expand_', 'zh_expand_')) for pid in practice.passages)
    assert not practice.validate_operational_bank()
    for language in ('ru', 'zh-CN'):
        for skill in ('reading', 'listening'):
            assert {p.id for p in practice.active_passages(skill, language)} == {
                p.id for p in preset.active_passages(skill, language)}


def test_overlay_cannot_replace_approved_content_and_reload_preserves_base(tmp_path):
    item = read_package(MANIFEST).items[0]
    overlay = tmp_path / 'overlay.jsonl'
    forged = item.passage.model_copy(update={'passage_ru': 'tampered'})
    overlay.write_text(json.dumps({'kind': 'passage', 'data': forged.model_dump(mode='json')}), encoding='utf-8')
    bank = PracticeBank(overlay).load()
    assert bank.passages[item.passage.id].passage_ru == item.passage.passage_ru
    assert bank.load_warnings
    overlay.write_text('', encoding='utf-8')
    bank.reload()
    assert len(bank.passages) == 66 and not bank.load_warnings


def test_training_plays_approved_recording_without_tts(monkeypatch, tmp_path):
    from ui import callbacks as cb
    from core.storage import LocalStorage
    monkeypatch.setattr(cb, 'STORAGE', LocalStorage(tmp_path / 'sessions', tmp_path / 'history'))
    def forbidden(*args, **kwargs):
        raise AssertionError('Approved recordings must not trigger replacement synthesis')
    monkeypatch.setattr(cb, '_training_audio_profile', forbidden)
    monkeypatch.setattr(cb, 'generate_dialogue_cached_tts', forbidden)
    result = cb.start_session_callback(
        'Training Mode', 'Listening', '0+', '0+', 'Short — 8 questions', 'Off',
        [], [], 'After each passage', False, True, 'Automatic natural Russian voice', 'Normal', '')
    state, bundle = result[:2]
    assert state.status == 'active' and bundle['passage']['id'] in cb.PRESET_BANK.passages
    played = cb.play_audio_callback(state, bundle)
    assert 'approved fixed recording' in played[3]['value']
    assert 'audio' in played[1]['value']
