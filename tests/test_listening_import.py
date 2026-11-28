import base64
import hashlib
from pathlib import Path

import pytest

from core.preset_bank import ROOT, PresetBank, read_package, validate_item
from core.source_credits import assessment_credits
from scripts.curate_assessment import promote
from scripts.import_listening_review import import_files, parse_reviews
from scripts.preview_listening_pack import accept_audio_event, listening_score

PACK = ROOT / 'data/content_packs/ru-authentic-listening-pilot-01'
HTML = PACK / 'versions/v1/listening_review.html'
MD = PACK / 'versions/v1/listening_review.md'


def test_recovered_audio_text_questions_and_drafts():
    from bs4 import BeautifulSoup
    package = read_package(PACK/'package.json')
    assert len(package.items) == 6 and sum(len(i.questions) for i in package.items) == 17
    assert [len(i.questions) for i in package.items] == [2,3,3,3,3,3]
    for item,audio in zip(package.items,BeautifulSoup(HTML.read_bytes(),'html.parser').select('audio')):
        validate_item(item,PACK)
        assert item.review.status == 'draft' and not item.review.reuse_attested
        assert item.audio.source_type == 'authentic/open-licensed' and not item.audio.synthetic_tts
        assert not item.audio.validated and item.passage.calibrated_difficulty is None
        blob=(PACK/item.audio.path).read_bytes()
        assert blob == base64.b64decode(audio['src'].split(',',1)[1])
        assert hashlib.sha256(blob).hexdigest() == item.audio_sha256
        assert item.passage.passage_ru == ' '.join(c['text'] for c in item.authoring_record['captions'])
    bank = PresetBank(PACK/'package.json',PACK).load()
    assert bank.pending_count == 6 and not bank.passages and not bank.audio_assets
    assert not set(i.id for i in package.items) & set(PresetBank().load().passages)


def test_idempotent_import_and_immutable_originals(tmp_path):
    output = tmp_path/'draft/package.json'
    pack=import_files(HTML,MD,output)
    first=output.read_bytes()
    assert import_files(HTML,MD,output) == pack
    assert output.read_bytes()==first
    assert (output.parent/'versions/v1/listening_review.html').read_bytes()==HTML.read_bytes()
    changed=tmp_path/'changed.html'
    changed.write_bytes(HTML.read_bytes()+b'\n<!-- changed submission -->')
    with pytest.raises(ValueError,match='increase --version'):
        import_files(changed,MD,output)
    import_files(changed,MD,output,2)
    assert (output.parent/'versions/v1/package.json').read_bytes()==first
    assert read_package(output).items[0].content_version==2


@pytest.mark.parametrize('case',['key','choice','evidence','transcript','audio','license'])
def test_mismatched_source_is_rejected(case):
    html,md=HTML.read_bytes(),MD.read_bytes()
    if case=='key': html=html.replace(b'Answer: B',b'Answer: A',1)
    elif case=='choice': html=html.replace(b'She is sociable in everyday life',b'She is quiet in everyday life',1)
    elif case=='evidence': md=md.replace('c2 · 00:02.96–00:06.11'.encode(),'c2 · 00:02.96–00:07.11'.encode(),1)
    elif case=='transcript': html=html.replace('это другие ощущения.'.encode(),'это другое.'.encode(),1)
    elif case=='audio': html=html.replace(b'data:audio/mpeg;base64,',b'https://example.test/audio?data=',1)
    else: html=html.replace(b'https://creativecommons.org/licenses/by/3.0/',b'https://creativecommons.org/licenses/by/4.0/')
    with pytest.raises(ValueError): parse_reviews(html,md)


def test_corrupt_audio_rejected_and_no_partial_package(tmp_path):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(HTML.read_bytes(),'html.parser')
    soup.audio['src']='data:audio/mpeg;base64,'+base64.b64encode(b'invalid audio').decode()
    bad=tmp_path/'bad.html';bad.write_text(str(soup),encoding='utf-8')
    output=tmp_path/'draft/package.json'
    with pytest.raises(ValueError,match='decoding'):
        import_files(bad,MD,output)
    assert not output.exists()


def test_audio_event_order_and_late_events():
    state={'session_id':'s','passage_id':'p','phase':0,'finished':False}
    assert accept_audio_event(state,'s|p|end2')==state
    assert accept_audio_event(state,'other|p|start1')==state
    for phase in ('start1','end1','start2','end2'):
        updated=accept_audio_event(state,'s|p|'+phase)
        assert updated['phase']==state['phase']+1
        assert accept_audio_event(updated,'s|p|'+phase)==updated
        state=updated
    assert state['phase']==4
    assert accept_audio_event(state,'s|p|start1')==state


def test_report_distinguishes_audio_and_caption_licenses():
    item=read_package(PACK/'package.json').items[0]
    report=listening_score(item,[q.correct_key for q in item.questions])
    assert '2 of 2 correct' in report and 'No proficiency level' in report
    assert 'Sources for your listening' in report and 'Reading passage' not in report
    assert 'Audio license:' in report and 'CC BY 3.0' in report
    assert 'CC BY-SA 4.0' in report and 'Fixed caption revision' in report
    assert item.passage.provenance['source_original_url'] in report
    assert item.passage.provenance['caption_source_url'] in report
    with pytest.raises(ValueError): listening_score(item,[None,None])
    from core.adaptive import initialize_ability
    from core.models import SessionState
    from core.session import activate_bundle
    state=SessionState(mode='assessment',selected_skills=['listening'],session_started_at_epoch=0,
        reading_ability=initialize_ability('reading'),listening_ability=initialize_ability('listening'))
    activate_bundle(state,item.passage,item.questions)
    assert assessment_credits(state)==''
    state.status='stopped'
    assert 'Sources for your listening' in assessment_credits(state)


def approved_fixture(tmp_path):
    manifest=tmp_path/'data/assessment/bank.json'
    for item in read_package(PACK/'package.json').items:
        promote(PACK/'package.json',item.id,'Test fixture only','Fixture auditory/rights approval',True,manifest,tmp_path)
    return PresetBank(manifest,tmp_path).load()


def test_authentic_release_and_tts_safeguards(tmp_path):
    from scripts.package_demo import package_files
    bank=approved_fixture(tmp_path)
    for name in ('app.py','requirements.txt','LICENSE','data/assessment/audio/NOTICE.md','data/assessment/audio_license_audit.json'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
    paths=package_files(tmp_path)
    assert len([p for p in paths if p.suffix=='.mp3'])==6
    from scripts.package_demo import validate_authentic_audio
    item=next(iter(bank.reviewed_items.values())).model_dump(mode='json')
    item['audio']['synthetic_tts']=True
    with pytest.raises(ValueError): validate_authentic_audio(item,tmp_path)
    item['audio']['synthetic_tts']=False
    item['passage']['provenance'].pop('caption_license_url')
    with pytest.raises(ValueError,match='attribution'): validate_authentic_audio(item,tmp_path)


def test_approved_fixture_in_existing_demo_two_listens_and_end_citations(monkeypatch,tmp_path):
    from ui import demo
    from core.storage import LocalStorage
    bank=approved_fixture(tmp_path)
    monkeypatch.setattr(demo.cb,'PRESET_BANK',bank)
    monkeypatch.setattr(demo.cb,'STORAGE',LocalStorage(tmp_path/'sessions',tmp_path/'history'))
    monkeypatch.setattr(demo.cb,'EXPORT_DIR',tmp_path/'exports')
    for key in ('OPENAI_API_KEY','ELEVENLABS_API_KEY','ANTHROPIC_API_KEY','HF_TOKEN'):
        monkeypatch.delenv(key,raising=False)
    result=demo.start_demo('Russian','Listening')
    seen=set()
    while result[0].status=='active':
        state,bundle,nonce=result[:3]
        assert state.current_passage_id not in seen
        seen.add(state.current_passage_id)
        item=bank.reviewed_items[state.current_passage_id]
        visible=str(result[3:])
        assert item.passage.passage_ru not in visible
        assert item.passage.provenance['source_title'] not in visible
        assert 'source_original_url' not in visible and not result[-4]['interactive']
        for phase in ('start1','end1','start2','end2'):
            demo.audio_event(state,f'{state.session_id}|{state.current_passage_id}|{phase}')
        answers=[q['correct_key'] for q in bundle['questions']]
        result=demo.submit_demo(state,bundle,nonce,*answers,*([None]*(5-len(answers))))
    assert result[0].completed_count('listening')>=12
    assert 'Sources for your listening' in result[-3]['value']
    assert 'CC BY 3.0' in result[-3]['value'] and 'CC BY-SA 4.0' in result[-3]['value']


def test_draft_media_excluded_from_current_deployment():
    from scripts.package_demo import package_files
    names=[str(p.relative_to(ROOT)) for p in package_files()]
    assert not any('content_packs' in n for n in names)
