"""Simple language and skill selection over the adaptive simulation engine."""
from pathlib import Path
import html
import time

import gradio as gr

from core.audio import gradio_audio_url
from core.constants import SIMULATION_MODE_LABEL
from core.demo_reporting import build_demo_report
from core.demo_hosting import is_hosted_demo
from core.session import mark_listening_play
from ui import callbacks as cb
from ui.components import answer_radio
from ui.layout import CUSTOM_CSS as BASE_CSS

CUSTOM_CSS = BASE_CSS + """
.demo-shell {max-width: 1180px; margin: 24px auto;}
.demo-setup {max-width: 760px; width: 100%; margin: 0 auto;}
.demo-test {border: 2px solid #25256b; border-radius: 4px; overflow: hidden; gap: 0 !important;}
.demo-test-title {background: #25256b; color: white; padding: 10px 18px; font-weight: 700;}
.demo-panels {gap: 0 !important; align-items: stretch; background: var(--background-fill-primary);}
.demo-pane {padding: 20px !important; min-width: 0 !important; flex-wrap: nowrap !important; overflow-anchor: none;}
.demo-pane > * {flex-shrink: 0 !important; min-width: 0 !important; width: 100%;}
.demo-reading .demo-pane {height: clamp(380px, 60vh, 680px); overflow-y: auto; scrollbar-gutter: stable;}
.demo-reading .demo-source {border-right: 2px solid #b5b5ca;}
.demo-test .passage-card {border: 0; border-radius: 0; padding: 0; line-height: 1.8;}
.demo-end-marker {border-top: 2px solid #be4b55; padding-top: 8px; margin-top: 18px; color: var(--body-text-color-subdued); font-size: .8rem;}
.demo-listening .demo-panels {flex-direction: column;}
.demo-listening .demo-source, .demo-listening .demo-questions {flex-basis: auto !important;}
.demo-listening .demo-source .demo-end-marker {display: none;}
.demo-status-bar {border-top: 2px solid #25256b; padding: 12px; align-items: center; gap: 14px; background: var(--background-fill-secondary);}
.demo-status-bar > * {min-width: 150px !important;}
.demo-status-bar .timer-card {margin: 0;}
@media (max-width: 700px) {
  .demo-shell {margin: 12px auto;}
  .demo-reading .demo-panels {flex-direction: column;}
  .demo-reading .demo-pane {height: auto; max-height: none; overflow: visible;}
  .demo-reading .demo-source {border-right: 0; border-bottom: 2px solid #b5b5ca;}
  .demo-pane {padding: 14px !important;}
}
.demo-intro {color: #667085; font-size: 1.05rem;}
.demo-audio button {padding: 12px 22px; border-radius: 9px; border: 1px solid #345995; cursor: pointer; font: inherit;}
.demo-audio [data-demo-status] {margin-top: 12px;}
.demo-result {padding: 24px; border: 1px solid var(--border-color-primary); border-radius: 12px;}
.demo-result p {margin: 12px 0; line-height: 1.55;}
.demo-result h2 {font-size: 1.4rem; margin-bottom: 20px;}
.demo-result h3 {font-size: 1.1rem; margin: 20px 0 10px;}
.demo-result .demo-result-label {margin-bottom: 0;}
.demo-result .demo-result-level {font-size: 2rem; font-weight: 700; margin-top: 0;}
.demo-result-confidence {border-left: 4px solid #b88326; padding: 12px 18px; margin: 18px 0; background: var(--background-fill-secondary);}
.demo-result table {width: 100%; border-collapse: collapse;}
.demo-result th, .demo-result td {text-align: left; padding: 8px; border-bottom: 1px solid var(--border-color-primary);}
.demo-result details {border-top: 1px solid var(--border-color-primary); padding: 14px 0;}
.demo-result summary {cursor: pointer; font-weight: 600;}
.demo-result h4 {margin-top: 18px; font-weight: 600;}
.demo-result-note {font-size: .9rem; color: var(--body-text-color-subdued);}
"""
AUDIO_JS = Path(__file__).with_name('demo_audio.js').read_text(encoding='utf-8')
TIMER_JS = r"""
const bind = () => {
  const clock = document.getElementById('demo-section-timer')?.querySelector('[data-demo-deadline]');
  if (clock && document.demoPanePassage !== clock.dataset.demoPassage) {
    // Wait for Gradio's other outputs to settle before resetting their scroll.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!clock.isConnected) return;
      for (const [id, label] of [['demo-source-pane', 'Passage'], ['demo-question-pane', 'Questions']]) {
        const pane = document.getElementById(id);
        if (pane) {
          pane.scrollTop = 0; pane.scrollLeft = 0;
          pane.tabIndex = 0; pane.setAttribute('role', 'region'); pane.setAttribute('aria-label', label);
        }
      }
    }));
    document.demoPanePassage = clock.dataset.demoPassage;
  }
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
document.demoTimerObserver.observe(document.body, {childList: true, subtree: true,
  attributes: true, attributeFilter: ['data-demo-passage']});
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
    finished = bool(state and state.status != 'active')
    if finished:
        status = gr.update(value='', visible=False)
    report = gr.update(value=build_demo_report(state) if finished else '', visible=finished)
    audio = (gr.skip() if preserve_audio else gr.update(
        value=audio_markup(state, bundle) if listening else '', visible=bool(listening)))
    can_submit = active and (not listening or state.current_listening_completed == 2)
    timer = gr.update(value=(f'<div class="timer-card" data-demo-passage="{html.escape(state.current_passage_id, quote=True)}" data-demo-deadline="{int(state.skill_deadline_epoch * 1000)}" role="timer">Time remaining</div>'
                             if active else ''), visible=active)
    return [state, bundle, nonce, status, timer, result[5], result[6], audio,
            *result[10:TAIL],
            gr.update(visible=active, elem_classes=['demo-test', 'demo-listening' if listening else 'demo-reading']),
            gr.update(value='Submit answers', visible=active, interactive=can_submit),
            report, gr.update(visible=not active),
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
    else:
        # Setup failures must remain visible while the test panel is hidden.
        message = result[3].get('value', '') if isinstance(result[3], dict) else str(result[3])
        raise gr.Error(message or 'Unable to begin a test. Check that approved passages are available.')
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
    expired_skill = (state.active_skill if state and state.status == 'active'
                     and state.skill_deadline_epoch is not None
                     and time.time() >= state.skill_deadline_epoch else None)
    if expired_skill:
        state.assessment_end_reasons[expired_skill] = 'time_limit'
    result = cb.expire_section_callback(state, bundle, nonce)
    unchanged = bool(result[1] and bundle and result[1]['passage']['id'] == bundle['passage']['id'])
    return present(result, preserve_audio=unchanged)


def restore_demo(request: gr.Request):
    """Optional checkpoint link without extra setup controls."""
    code = request.query_params.get('resume', '')
    if not code:
        return [gr.skip()] * (13 + cb.MAX_SLOTS * 2)
    if is_hosted_demo():
        raise gr.Error('Saved-report links are available only in the local demo. Begin a new test here.')
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
            report = gr.HTML(visible=False)
            state, bundle, nonce = gr.State(), gr.State(), gr.State()
            with gr.Column(elem_classes=['demo-setup']) as setup:
                language = gr.Radio(['Russian', 'Chinese'], value='Russian', label='Choose your language')
                skill = gr.Radio(['Reading', 'Listening'], value='Reading', label='Choose your test')
                gr.Markdown('**One skill per test** · 12 questions · up to 30 minutes.\n\n'
                            'In Listening, each recording plays twice, with a beep between listens. Answer every question, then submit. '
                            'You cannot return to a submitted passage. Results appear at the end.')
                begin = gr.Button('Begin test', variant='primary')
            with gr.Column(visible=False, elem_classes=['demo-test']) as test:
                gr.HTML('<div class="demo-test-title">Language comprehension · Practice assessment</div>')
                with gr.Row(elem_classes=['demo-panels']):
                    with gr.Column(scale=1, min_width=0, elem_classes=['demo-pane', 'demo-source'], elem_id='demo-source-pane'):
                        orientation = gr.Markdown(visible=False)
                        passage = gr.Markdown(visible=False, elem_classes=['passage-card'])
                        audio = gr.HTML(visible=False, js_on_load=AUDIO_JS, elem_id='demo-audio-player')
                        gr.HTML('<div class="demo-end-marker">End of passage</div>')
                    with gr.Column(scale=1, min_width=0, elem_classes=['demo-pane', 'demo-questions'], elem_id='demo-question-pane'):
                        gr.Markdown('### Questions')
                        question_outputs, answers = [], []
                        for i in range(cb.MAX_SLOTS):
                            question_outputs.append(gr.Markdown(visible=False))
                            answer = answer_radio(visible=False, label=f'Question {i+1}')
                            question_outputs.append(answer)
                            answers.append(answer)
                        gr.HTML('<div class="demo-end-marker">End of questions for this passage</div>')
                with gr.Row(elem_classes=['demo-status-bar']):
                    status = gr.Markdown(visible=False)
                    timer = gr.HTML(visible=False, js_on_load=TIMER_JS, elem_id='demo-section-timer')
                    submit = gr.Button('Submit answers', variant='primary', visible=False)
            event = gr.Textbox(elem_id='demo-audio-event', elem_classes=['event-bridge'])
            confirm_audio = gr.Button('Audio event', elem_id='demo-audio-confirm', elem_classes=['event-bridge'])
            expired = gr.Button('Timer event', elem_id='timer-expired-trigger', elem_classes=['event-bridge'])
            outputs = [state, bundle, nonce, status, timer, orientation, passage, audio,
                       *question_outputs, test, submit, report, setup, begin]
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
