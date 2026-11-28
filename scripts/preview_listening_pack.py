"""Local instructor preview: authentic audio, two listens, and end-only review."""
import argparse
from html import escape
import os
from pathlib import Path
import sys
from uuid import uuid4

os.environ.setdefault('PYTHON_DOTENV_DISABLED', '1')
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gradio as gr
from core.audio import gradio_audio_url
from core.config import get_settings
from core.preset_bank import ROOT, local_asset, read_package, validate_item
from core.source_credits import credits_html, source_snapshot
from core.storage import LocalStorage
from ui.components import answer_radio

DEFAULT_PACKAGE = ROOT / 'data/content_packs/ru-authentic-listening-pilot-01/package.json'
AUDIO_JS = (ROOT / 'ui/demo_audio.js').read_text(encoding='utf-8')
CSS = '.event-bridge {display:none !important;} .listening-preview {max-width:1100px; margin:auto;} .demo-audio button {padding:12px;cursor:pointer;} .source-credits p {margin:12px 0;} .source-credits a {text-decoration:underline;}'


def accept_audio_event(state, event):
    if not state or state.get('finished'):
        return state
    parts = (event or '').split('|')
    phases = ('start1', 'end1', 'start2', 'end2')
    n = state['phase']
    if len(parts) == 3 and parts[:2] == [state['session_id'], state['passage_id']] and n < 4 and parts[2] == phases[n]:
        return {**state, 'phase': n+1}
    return state


def listening_score(item, answers):
    if len(answers) != len(item.questions) or any(a not in q.choices for q,a in zip(item.questions,answers)):
        raise ValueError('Choose an answer for every question.')
    right = sum(a == q.correct_key for q,a in zip(item.questions,answers))
    missed = sorted({q.answer_position_metadata['source_skill'].replace('_',' ') for q,a in zip(item.questions,answers) if a != q.correct_key})
    rows = [f'<h2>Preview complete · {right} of {len(answers)} correct</h2>',
            '<p>Teacher-review draft. No proficiency level is estimated or diagnostic result saved.</p>',
            '<p>Skills to review: ' + escape(', '.join(missed) if missed else 'None missed in this excerpt') + '</p>',
            '<details><summary>Published timed transcript · CC BY-SA 4.0</summary>']
    rows.extend(f'<p><strong>{escape(c["timing"])}</strong> {escape(c["text"])}</p>' for c in item.authoring_record['captions'])
    rows.append('<p>Published caption wording is retained. Timing is rounded in the supplied review; '
                'some final caption endpoints exceed decoded audio by a fraction of a second. Alignment and accuracy await teacher audition.</p></details>')
    for n,q in enumerate(item.questions,1):
        source = item.authoring_record['questions'][n-1]
        rows += [f'<h3>{n}. {escape(q.stem_en)}</h3>', f'<p>Correct answer: {q.correct_key}. {escape(q.choices[q.correct_key])}</p>',
                 f'<p>{escape(q.rationale_en)}</p>']
        rows.extend(f'<p>Evidence ({escape(e["caption_id"])} · {escape(e["timing"])}): {escape(e["quote_ru"])}</p>' for e in source['evidence'])
        rows.append('<details><summary>Distractor review</summary>')
        rows.extend(f'<p>{k}: {escape(v)}</p>' for k,v in source['option_rationales'].items())
        rows.append('</details>')
    rows += ['<details><summary>Instructor review notes</summary>',
             f'<p>Transcript-based target: ILR {escape(item.passage.target_ilr)}; uncalibrated.</p>',
             f'<p>{escape(item.passage.provenance["difficulty_rationale"])}</p>',
             f'<p>{escape(item.passage.provenance["auditory_review_focus"])}</p></details>',
             credits_html({item.id:source_snapshot(item.passage)})]
    return ''.join(rows)


def build_preview(package_path=DEFAULT_PACKAGE):
    items = {i.id:i for i in read_package(package_path).items}
    settings = get_settings()
    storage = LocalStorage(settings.session_runtime_path(ROOT),settings.history_runtime_path(ROOT))

    def start(pid, profile):
        item = items[pid]
        validate_item(item, package_path.parent)
        if profile.strip():
            history = storage.load_history(profile.strip()+'__ru')
            history.seen_family_ids = sorted(set(history.seen_family_ids) | {item.passage.family_id})
            storage.save_history(history)
        state = {'session_id':uuid4().hex, 'passage_id':pid, 'phase':0, 'finished':False}
        url = escape(gradio_audio_url(local_asset(package_path.parent,item.audio.path)),quote=True)
        player = f'<div class="demo-audio"><audio data-demo-audio="true" data-session="{state["session_id"]}" data-passage="{pid}" data-round="1" data-started="false" src="{url}" preload="metadata" playsinline></audio><button type="button" data-demo-play>Play passage · two listens</button><div data-demo-status role="status" aria-live="polite">Listen twice, with a beep between plays.</div></div>'
        updates = []
        for n in range(3):
            q = item.questions[n] if n < len(item.questions) else None
            updates.append(gr.update(visible=q is not None, label=f'{n+1}. {q.stem_en}' if q else '',
                choices=[(f'{k}. {v}',k) for k,v in q.choices.items()] if q else [],value=None))
        return [state,gr.update(value=player,visible=True),*updates,gr.update(value='',visible=False),
                gr.update(visible=True,interactive=False)]

    def audio_event(state, event):
        updated = accept_audio_event(state,event)
        return updated,gr.update(interactive=bool(updated and updated['phase']==4 and not updated['finished']))

    def finish(state,*answers):
        if not state or state['phase'] != 4:
            raise gr.Error('Listen to both complete plays before finishing.')
        item = items[state['passage_id']]
        try:
            report = listening_score(item,answers[:len(item.questions)])
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc
        return {**state,'finished':True},gr.update(value=report,visible=True),gr.update(interactive=False)

    with gr.Blocks(title='Authentic listening · Instructor preview',analytics_enabled=False) as app:
        with gr.Column(elem_classes=['listening-preview']):
            gr.Markdown('# Authentic Russian listening\n\n**Six teacher-review drafts · 17 questions.** '
                'Listen at normal speed before reviewing the published captions. '
                'Each excerpt plays twice with a beep between listens. Transcripts, answers and source credits appear after you finish.')
            with gr.Row():
                choice = gr.Dropdown([(f'Listening passage {n} · {i.audio.duration_seconds:.1f} seconds',i.id)
                    for n,i in enumerate(items.values(),1)],value=next(iter(items)),label='Choose a passage')
                profile = gr.Textbox(label='Optional local profile ID',info='Use the same local profile to exclude this family from fresh diagnostic evidence. Anonymous cross-device tracking is unavailable.')
            state = gr.State()
            start_button = gr.Button('Open passage',variant='primary')
            with gr.Row():
                with gr.Column():
                    gr.Markdown('### Listening passage\n\nA short excerpt from a radio broadcast. Source speech; no generated narration.')
                    audio = gr.HTML(visible=False,js_on_load=AUDIO_JS,elem_id='demo-audio-player')
                with gr.Column():
                    answers = [answer_radio(label=f'Question {n+1}',visible=False) for n in range(3)]
            finish_button = gr.Button('Finish preview and review',visible=False,interactive=False,variant='primary')
            report = gr.HTML(visible=False)
            event = gr.Textbox(elem_id='demo-audio-event',elem_classes=['event-bridge'])
            confirm = gr.Button('Audio event',elem_id='demo-audio-confirm',elem_classes=['event-bridge'])
            common = dict(api_visibility='private',concurrency_id='listening-preview',concurrency_limit=1)
            start_button.click(start,[choice,profile],[state,audio,*answers,report,finish_button],**common)
            confirm.click(audio_event,[state,event],[state,finish_button],
                js="(s,e) => [s, document.querySelector('#demo-audio-event textarea, #demo-audio-event input').value]",**common)
            finish_button.click(finish,[state,*answers],[state,report,finish_button],**common)
        app.queue()
    return app


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,default=DEFAULT_PACKAGE)
    p.add_argument('--port',type=int,default=7868)
    args = p.parse_args()
    build_preview(args.package).launch(server_name='127.0.0.1',server_port=args.port,share=False,css=CSS,ssr_mode=False,footer_links=[],
        allowed_paths=[str((args.package.parent/'audio').resolve())],
        blocked_paths=[str(args.package.resolve()),str((args.package.parent/'versions').resolve()),
                       str(ROOT/'data/assessment/bank.json'),str(ROOT/'.env'),str(ROOT/'.git'),str(ROOT/'storage')])
