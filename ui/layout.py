from __future__ import annotations

import gradio as gr

from core.constants import DISCLAIMER, ILR_LEVELS, QUESTION_TYPES
from ui.callbacks import (
    CONTENT_SOURCE_CHOICES,
    MAX_SLOTS,
    PROVIDER_MESSAGE,
    PROVIDER_READY,
    QUEUE_CONCURRENCY_LIMIT,
    TOPICS,
    abandon_strict_callback,
    answer_changed_callback,
    mode_controls,
    play_audio_callback,
    resume_session_callback,
    show_hints_callback,
    start_session_callback,
    stop_training_callback,
    submit_passage_callback,
)


AUDIO_HTML_JS = r"""
const bindAudio = () => {
  const audio = element.querySelector('audio[data-controlled-audio="true"]');
  const status = element.querySelector('[data-audio-status="true"]');
  if (!audio || !status || audio.dataset.bound === 'true') return;
  audio.dataset.bound = 'true';
  audio.controls = false;

  const setStatus = (message) => { status.textContent = message; };
  audio.addEventListener('playing', () => setStatus('Playing audio…'), { once: true });
  audio.addEventListener('ended', () => {
    setStatus(audio.dataset.completion || 'Playback completed.');
    if (audio.dataset.strict === 'true') {
      audio.removeAttribute('src');
      audio.load();
    }
  }, { once: true });
  audio.addEventListener('error', () => {
    setStatus('Audio could not play. Your completed work remains saved. Press Play Audio once more or continue after the app recovers.');
  }, { once: true });

  const playResult = audio.play();
  if (playResult && typeof playResult.catch === 'function') {
    playResult.catch(() => setStatus('Browser autoplay was blocked. Press Play / Replay Audio again.'));
  }
};
watch('value', bindAudio);
bindAudio();
"""

CUSTOM_CSS = """
:root { --card-border: rgba(127,127,127,.28); }
.app-shell { max-width: 1220px; margin: 0 auto; }
.disclaimer { border-left: 5px solid #8b1e1e; padding: 12px 16px; background: rgba(139,30,30,.08); border-radius: 8px; }
.mode-card { border: 1px solid var(--card-border); border-radius: 14px; padding: 14px; height: 100%; }
.orientation { border-left: 5px solid #345995; padding: 12px 16px; background: rgba(52,89,149,.08); border-radius: 8px; }
.passage-card { border: 1px solid var(--card-border); border-radius: 14px; padding: 18px; font-size: 1.06rem; line-height: 1.65; }
.timer-card { font-weight: 700; font-size: 1.05rem; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--card-border); width: fit-content; }
.timer-card.strict { border-color: #8b1e1e; }
.report-panel { max-height: 720px; overflow-y: auto; border: 1px solid var(--card-border); border-radius: 14px; padding: 18px; }
.controlled-audio-wrap { padding: 12px; border: 1px solid var(--card-border); border-radius: 12px; }
@media (max-width: 760px) { .passage-card { padding: 12px; font-size: 1rem; } }
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Russian Adaptive Proficiency Practice") as demo:
        with gr.Column(elem_classes=["app-shell"]):
            gr.Markdown("# Russian Adaptive Proficiency Practice")
            gr.Markdown(DISCLAIMER, elem_classes=["disclaimer"])
            with gr.Row():
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Training Mode**\n\nTargeted practice, replay, optional hints, and passage-level review.")
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Adaptive Diagnostic**\n\nIndependent Reading and Listening estimates with uncertainty and confidence-based stopping.")
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Full CA Simulation**\n\nStrict timing, locked progression, one controlled listening play, and no feedback until completion.")

            state = gr.State(value=None)
            bundle_state = gr.State(value=None)
            nonce_state = gr.State(value=None)

            with gr.Accordion("Session Setup", open=True):
                with gr.Row():
                    mode = gr.Radio(["Training Mode", "Adaptive Diagnostic", "Full CA Simulation"], value="Training Mode", label="Mode")
                    skill = gr.Radio(["Reading", "Listening", "Reading + Listening (separate sections)"], value="Reading", label="Skill selection")
                with gr.Row():
                    start_level = gr.Dropdown(ILR_LEVELS, value="1+", label="Approximate starting ILR band")
                    target_level = gr.Dropdown(ILR_LEVELS, value="2", label="Target ILR band")
                    length = gr.Dropdown(["Short — 8 questions", "Standard — 16 questions", "Long — 24 questions"], value="Standard — 16 questions", label="Session length")
                    timer_mode = gr.Dropdown(["Off", "Standard count-up", "Strict countdown"], value="Off", label="Timer behavior")
                with gr.Row():
                    topics = gr.CheckboxGroup(TOPICS, label="Topics (leave blank for balanced selection)")
                    competencies = gr.CheckboxGroup(QUESTION_TYPES, label="Comprehension competencies to emphasize")
                with gr.Row():
                    feedback_timing = gr.Radio(["After each passage", "End of session"], value="After each passage", label="Feedback timing")
                    hints_enabled = gr.Checkbox(value=False, label="Enable strategy hints")
                    transcript_review = gr.Checkbox(value=True, label="Show listening transcript after answers are locked")
                with gr.Row():
                    voice = gr.Dropdown(["Russian Female — Svetlana", "Russian Male — Dmitry", "Starter-bank eSpeak voice"], value="Starter-bank eSpeak voice", label="Training voice preference")
                    speed = gr.Dropdown(["Very slow", "Slow", "Normal", "Fast"], value="Normal", label="Training audio speed")
                    profile_id = gr.Textbox(label="Optional local profile ID", placeholder="Used only for history and repeat-exposure control")
                with gr.Row():
                    content_source = gr.Dropdown(
                        CONTENT_SOURCE_CHOICES,
                        value=CONTENT_SOURCE_CHOICES[0],
                        label="Content source",
                        info="Fresh AI is constrained to assessment authoring, validated before use, saved to the bank, and automatically falls back on any failure.",
                    )
                provider_icon = "✅" if PROVIDER_READY else "ℹ️"
                gr.Markdown(f"{provider_icon} **Live generation status:** {PROVIDER_MESSAGE}")
                start_btn = gr.Button("Begin Session", variant="primary")

            with gr.Accordion("Recover a Checkpoint", open=False):
                with gr.Row():
                    resume_code = gr.Textbox(label="Session code", placeholder="Example: 4e1ac9f71c2b")
                    resume_btn = gr.Button("Resume Session")

            status = gr.Markdown(visible=False)
            timer = gr.HTML(visible=False)
            orientation = gr.Markdown(visible=False, elem_classes=["orientation"])
            passage = gr.Markdown(visible=False, elem_classes=["passage-card"])
            audio_error = gr.Markdown(visible=False)
            play_btn = gr.Button("Play / Replay Audio", visible=False)
            audio_html = gr.HTML(visible=False, js_on_load=AUDIO_HTML_JS, elem_id="controlled-listening-audio")

            question_markdowns = []
            answer_radios = []
            for index in range(MAX_SLOTS):
                question_markdowns.append(gr.Markdown(visible=False))
                answer_radios.append(gr.Radio(choices=[], visible=False, label=f"Question {index + 1}"))

            with gr.Row():
                hint_btn = gr.Button("Show Strategy Hints", visible=False)
                submit_btn = gr.Button("Submit Passage", variant="primary", visible=False)
            hint_output = gr.Markdown(visible=False)
            feedback_output = gr.Markdown(visible=False, elem_classes=["report-panel"])

            with gr.Row():
                stop_training_btn = gr.Button("Stop Training & Show Partial Report", visible=False)
                abandon_btn = gr.Button("Abandon Diagnostic / Simulation", visible=False)
                confirm_abandon = gr.Checkbox(label="I understand this abandons the active strict session", visible=False)

            report = gr.Markdown(visible=False, elem_classes=["report-panel"])
            with gr.Row():
                json_export = gr.File(label="Session JSON", visible=False)
                csv_export = gr.File(label="Response CSV", visible=False)

            outputs = [
                state, bundle_state, nonce_state, status, timer, orientation, passage, audio_error,
                play_btn, audio_html,
            ]
            for q_md, radio in zip(question_markdowns, answer_radios):
                outputs.extend([q_md, radio])
            outputs.extend([
                hint_btn, hint_output, submit_btn, stop_training_btn, abandon_btn, confirm_abandon,
                feedback_output, report, json_export, csv_export,
            ])

            mode.change(
                mode_controls,
                inputs=[mode, skill],
                outputs=[length, timer_mode, hints_enabled, transcript_review, voice, speed, feedback_timing],
            )
            skill.change(
                mode_controls,
                inputs=[mode, skill],
                outputs=[length, timer_mode, hints_enabled, transcript_review, voice, speed, feedback_timing],
            )

            start_btn.click(
                start_session_callback,
                inputs=[
                    mode, skill, start_level, target_level, length, timer_mode, topics, competencies,
                    feedback_timing, hints_enabled, transcript_review, voice, speed, profile_id, content_source,
                ],
                outputs=outputs,
            )
            resume_btn.click(resume_session_callback, inputs=[resume_code], outputs=outputs)

            for index, radio in enumerate(answer_radios):
                radio.change(
                    lambda st, bd, value, slot=index: answer_changed_callback(st, bd, value, slot),
                    inputs=[state, bundle_state, radio],
                    outputs=[state],
                    queue=False,
                )

            play_btn.click(
                play_audio_callback,
                inputs=[state, bundle_state],
                outputs=[state, audio_html, play_btn, status],
            )
            hint_btn.click(show_hints_callback, inputs=[state, bundle_state], outputs=[hint_output])
            submit_btn.click(
                submit_passage_callback,
                inputs=[state, bundle_state, nonce_state, *answer_radios],
                outputs=outputs,
            )
            stop_training_btn.click(stop_training_callback, inputs=[state], outputs=outputs)
            abandon_btn.click(abandon_strict_callback, inputs=[state, confirm_abandon], outputs=outputs)

        demo.queue(default_concurrency_limit=QUEUE_CONCURRENCY_LIMIT, max_size=32)
    return demo
