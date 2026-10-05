"""Simple language and skill selection over the adaptive simulation engine."""
from pathlib import Path
import html

import gradio as gr

from core.audio import gradio_audio_url
from core.constants import SIMULATION_MODE_LABEL
from core.session import mark_listening_play
from ui import callbacks as cb
from ui.components import answer_radio
from ui.layout import CUSTOM_CSS as BASE_CSS

CUSTOM_CSS = BASE_CSS + """
.demo-shell {max-width: 850px; margin: 30px auto;}
.demo-intro {color: #667085; font-size: 1.05rem;}
.demo-audio button {padding: 12px 22px; border-radius: 9px; border: 1px solid #345995; cursor: pointer; font: inherit;}
.demo-audio [data-demo-status] {margin-top: 12px;}
"""
AUDIO_JS = Path(__file__).with_name('demo_audio.js').read_text(encoding='utf-8')
TIMER_JS = r"""
const bind = () => {
  const clock = document.getElementById('demo-section-timer')?.querySelector('[data-demo-deadline]');
  if (document.demoTimerClock === clock) return;
  if (document.demoTick) clearInterval(document.demoTick);
  document.demoTimerClock = clock;
  if (!clock) return;
  const draw = () => {
    if (!clock.isConnected) { clearInterval(document.demoTick); return; }
    const seconds = Math.max(0, Math.ceil((Number(clock.dataset.demoDeadline) - Date.now()) / 1000));
    clock.textContent = `Time remaining: ${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    if (!seconds && !clock.dataset.sent) {
      clock.dataset.sent = 'true';
      clearInterval(document.demoTick);
      const host = document.getElementById('timer-expired-trigger');
      const button = host && (host.querySelector('button') || host);
      if (button) button.click();
    }
  };
  document.demoTick = setInterval(draw, 1000); draw();
};
if (document.demoTimerObserver) document.demoTimerObserver.disconnect();
document.demoTimerObserver = new MutationObserver(bind);
document.demoTimerObserver.observe(document.body, {childList: true, subtree: true});
bind();
"""
TAIL = 10 + cb.MAX_SLOTS * 2


def audio_markup(state, bundle):
    if state.current_listening_completed >= 2:
        return '<div class="controlled-audio-wrap">Both listens complete. Submit your answers when ready.</div>'
    asset = cb.PRESET_BANK.get_audio(bundle['passage']['audio_asset_id'])
    source = html.escape(gradio_audio_url(asset.path), quote=True)
    return f'''<div class="controlled-audio-wrap demo-audio">
      <audio data-demo-audio="true" data-session="{state.session_id}"
        data-passage="{state.current_passage_id}" data-round="{state.current_listening_completed + 1}"
        data-started="{str(state.current_listening_plays > state.current_listening_completed).lower()}"
        src="{source}" preload="metadata" playsinline></audio>
      <button type="button" data-demo-play>Play passage · two listens</button>
      <div data-demo-status role="status" aria-live="polite">Listen twice, with a beep between plays.</div>
    </div>'''


def present(result, *, preserve_audio=False):
    """Map the full application's result into the deliberately small demo UI."""
    state, bundle, nonce = result[:3]
    active = bool(state and state.status == 'active' and bundle)
    listening = active and bundle['passage']['skill'] == 'listening'
    if active:
        section = state.active_skill.title()
        progress = f'**{section}** · {state.completed_count(state.active_skill)} of 12 questions completed'
        # Show actionable validation errors without the full administrative status.
        if state.last_error:
            progress += '\n\n' + html.escape(state.last_error)
        status = gr.update(value=progress, visible=True)
    else:
        status = result[3]
    audio = (gr.skip() if preserve_audio else gr.update(
        value=audio_markup(state, bundle) if listening else '', visible=bool(listening)))
    can_submit = active and (not listening or state.current_listening_completed == 2)
    timer = gr.update(value=(f'<div class="timer-card" data-demo-deadline="{int(state.skill_deadline_epoch * 1000)}" role="timer">Time remaining</div>'
                             if active else ''), visible=active)
    return [state, bundle, nonce, status, timer, result[5], result[6], audio,
            *result[10:TAIL],
            gr.update(value='Submit answers', visible=active, interactive=can_submit),
            result[TAIL + 7], gr.update(visible=not active),
            gr.update(value='Begin test' if not state else 'Start a new test', interactive=not active)]


def start_demo(language, skill='Reading'):
    if language not in ('Russian', 'Chinese'):
        raise gr.Error('Choose Russian or Chinese.')
    if skill not in ('Reading', 'Listening'):
        raise gr.Error('Choose Reading or Listening.')
    result = cb.start_session_callback(
        SIMULATION_MODE_LABEL, skill, '1+', '2',
        'Shortened practice — 12 questions per skill / 30 minutes', 'Strict countdown',
        [], [], 'End of session', False, False, 'Automatic natural Russian voice', 'Normal', '',
        language_label='Mandarin Chinese' if language == 'Chinese' else 'Russian', progress=None)
    state = result[0]
    if state:
        state.demo_mode = True
        cb.STORAGE.save_checkpoint(state)
    return present(result)


def audio_event(state, event):
    """Idempotent, ordered browser events bound to the current session/passage."""
    skip = (state, gr.skip(), gr.skip())
    if not state or not state.demo_mode or state.status != 'active' or state.active_skill != 'listening':
        return skip
    parts = (event or '').split('|')
    if len(parts) != 3 or parts[:2] != [state.session_id, state.current_passage_id]:
        return skip
    phase = parts[2]
    plays, completed = state.current_listening_plays, state.current_listening_completed
    expected = {(0, 0): 'start1', (1, 0): 'end1', (1, 1): 'start2', (2, 1): 'end2'}.get((plays, completed))
    if phase != expected:
        return skip
    if phase.startswith('start'):
        mark_listening_play(state)
    else:
        state.current_listening_completed += 1
    cb.STORAGE.save_checkpoint(state)
    done = state.current_listening_completed == 2
    return state, gr.update(interactive=done), gr.update(
        value=f'**Listening** · {state.completed_count("listening")} of 12 questions completed'
              + ('\n\nBoth listens complete. You can submit your answers.' if done else ''), visible=True)


def submit_demo(state, bundle, nonce, *answers):
    if not state or not state.demo_mode:
        raise gr.Error('Begin a demo test first.')
    prior = state.current_passage_id
    state.last_error = None
    result = cb.submit_passage_callback(state, bundle, nonce, *answers, progress=None)
    unchanged = bool(result[1] and result[0].current_passage_id == prior)
    return present(result, preserve_audio=unchanged)


def expire_demo(state, bundle, nonce):
    result = cb.expire_section_callback(state, bundle, nonce)
    unchanged = bool(result[1] and bundle and result[1]['passage']['id'] == bundle['passage']['id'])
    return present(result, preserve_audio=unchanged)


def restore_demo(request: gr.Request):
    """Optional checkpoint link without extra setup controls."""
    code = request.query_params.get('resume', '')
    if not code:
        return [gr.skip()] * (12 + cb.MAX_SLOTS * 2)
    saved = cb.STORAGE.load_checkpoint(code)
    if not saved.demo_mode:
        raise gr.Error('This checkpoint is not a demo test.')
    return present(cb.resume_session_callback(code, progress=None))


def build_app():
    with gr.Blocks(title='DLPT-style Adaptive Test · Demo', analytics_enabled=False) as app:
        with gr.Column(elem_classes=['app-shell', 'demo-shell']):
            gr.Markdown('# DLPT-style adaptive test')
            gr.Markdown('Choose a reading or listening test. Difficulty adapts as you answer.\n\n'
                        'Independent practice—not an official DLPT or an official score.', elem_classes=['demo-intro'])
            state, bundle, nonce = gr.State(), gr.State(), gr.State()
            with gr.Column() as setup:
                language = gr.Radio(['Russian', 'Chinese'], value='Russian', label='Choose your language')
                skill = gr.Radio(['Reading', 'Listening'], value='Reading', label='Choose your test')
                gr.Markdown('**One skill per test** · 12 questions · up to 30 minutes.\n\n'
                            'In Listening, each recording plays twice, with a beep between listens. Answer every question, then submit. '
                            'You cannot return to a submitted passage. Results appear at the end.')
                begin = gr.Button('Begin test', variant='primary')
            status = gr.Markdown(visible=False)
            timer = gr.HTML(visible=False, js_on_load=TIMER_JS, elem_id='demo-section-timer')
            orientation = gr.Markdown(visible=False)
            passage = gr.Markdown(visible=False, elem_classes=['passage-card'])
            audio = gr.HTML(visible=False, js_on_load=AUDIO_JS, elem_id='demo-audio-player')
            event = gr.Textbox(elem_id='demo-audio-event', elem_classes=['event-bridge'])
            confirm_audio = gr.Button('Audio event', elem_id='demo-audio-confirm', elem_classes=['event-bridge'])
            expired = gr.Button('Timer event', elem_id='timer-expired-trigger', elem_classes=['event-bridge'])
            question_outputs, answers = [], []
            for i in range(cb.MAX_SLOTS):
                question_outputs.append(gr.Markdown(visible=False))
                answer = answer_radio(visible=False, label=f'Question {i+1}')
                question_outputs.append(answer)
                answers.append(answer)
            submit = gr.Button('Submit answers', variant='primary', visible=False)
            report = gr.Markdown(visible=False)
            outputs = [state, bundle, nonce, status, timer, orientation, passage, audio,
                       *question_outputs, submit, report, setup, begin]
            common = dict(show_progress='minimal', concurrency_id='demo-events', concurrency_limit=1)
            app.load(restore_demo, outputs=outputs, **common)
            begin.click(start_demo, [language, skill], outputs, trigger_mode='once', **common)
            submit.click(submit_demo, [state, bundle, nonce, *answers], outputs, trigger_mode='once', **common)
            confirm_audio.click(audio_event, [state, event], [state, submit, status],
                                js="(s,e) => [s, document.querySelector('#demo-audio-event textarea, #demo-audio-event input').value]",
                                trigger_mode='multiple', **common)
            expired.click(expire_demo, [state, bundle, nonce], outputs, trigger_mode='once', **common)
        app.queue(default_concurrency_limit=1, max_size=32)
    return app
