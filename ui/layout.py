from __future__ import annotations

import gradio as gr

from core.constants import DISCLAIMER, ILR_LEVELS, QUESTION_TYPES
from ui.components import scalar_tolerant_checkbox_group
from ui.callbacks import (
    BANK_BOOTSTRAP_MESSAGE,
    BANK_STATUS_MESSAGE,
    CONTENT_SOURCE_CHOICES,
    MAX_SLOTS,
    PROVIDER_MESSAGE,
    PROVIDER_READY,
    QUEUE_CONCURRENCY_LIMIT,
    TOPICS,
    abandon_strict_callback,
    begin_activity,
    answer_changed_callback,
    end_activity,
    export_generated_bank_callback,
    import_generated_bank_callback,
    mode_controls,
    play_audio_callback,
    restore_activity_button,
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
.operation-activity { display:flex; align-items:center; gap:12px; padding:13px 15px; margin:10px 0; border:1px solid #345995; border-radius:12px; background:rgba(52,89,149,.09); }
.operation-spinner { width:22px; height:22px; flex:0 0 22px; border:3px solid rgba(52,89,149,.22); border-top-color:#345995; border-radius:50%; animation:operation-spin .8s linear infinite; }
@keyframes operation-spin { to { transform:rotate(360deg); } }
@media (max-width: 760px) { .passage-card { padding: 12px; font-size: 1rem; } }
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Russian Adaptive Proficiency Practice") as demo:
        with gr.Column(elem_classes=["app-shell"]):
            gr.Markdown("# Russian Adaptive Proficiency Practice")
            gr.Markdown(DISCLAIMER, elem_classes=["disclaimer"])
            with gr.Row():
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Training Mode**\n\nTargeted practice, replay, optional hints, and passage-level review with item-level disclosure.")
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Adaptive Diagnostic**\n\nIndependent Reading and Listening estimates. Item levels stay hidden during testing and appear in the final report.")
                with gr.Column(elem_classes=["mode-card"]):
                    gr.Markdown("**Full CA Simulation**\n\nStrict timing and locked progression. Item levels remain hidden until the completed final report.")

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
                    topics = scalar_tolerant_checkbox_group(TOPICS, label="Topics (leave blank for balanced selection)")
                    competencies = scalar_tolerant_checkbox_group(QUESTION_TYPES, label="Comprehension competencies to emphasize")
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
                bank_status = gr.Markdown(f"💾 **Reusable bank status:** {BANK_STATUS_MESSAGE}")
                if BANK_BOOTSTRAP_MESSAGE:
                    gr.Markdown(f"<small>{BANK_BOOTSTRAP_MESSAGE}</small>")
                start_btn = gr.Button("Begin Session", variant="primary")

            with gr.Accordion("Recover a Checkpoint", open=False):
                with gr.Row():
                    resume_code = gr.Textbox(label="Session code", placeholder="Example: 4e1ac9f71c2b")
                    resume_btn = gr.Button("Resume Session")

            with gr.Accordion("Generated Bank Backup & Persistence", open=False):
                gr.Markdown(
                    "Generated content must live outside the disposable Space container to survive restarts. "
                    "When private Dataset synchronization is active, the bank restores automatically. "
                    "The manual ZIP backup remains available as an additional safety copy."
                )
                with gr.Row():
                    export_bank_btn = gr.Button("Download Generated Bank Backup")
                    bank_backup_file = gr.File(label="Generated bank backup", visible=False)
                with gr.Row():
                    bank_import_file = gr.File(
                        label="Import a prior generated-bank ZIP or JSONL",
                        file_types=[".zip", ".jsonl"],
                        type="filepath",
                    )
                    import_bank_btn = gr.Button("Import and Merge Backup")
                bank_backup_status = gr.Markdown(visible=False)

            activity = gr.HTML(value="", visible=False, elem_id="operation-activity")
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
                feedback_output, report, json_export, csv_export, bank_status,
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

            start_prepare = start_btn.click(
                lambda: begin_activity("Starting session and loading the first passage…", "Starting…"),
                outputs=[activity, start_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            start_run = start_prepare.then(
                start_session_callback,
                inputs=[
                    mode, skill, start_level, target_level, length, timer_mode, topics, competencies,
                    feedback_timing, hints_enabled, transcript_review, voice, speed, profile_id, content_source,
                ],
                outputs=outputs,
                show_progress="hidden",
                trigger_mode="once",
            )
            start_run.then(
                lambda: restore_activity_button("Begin Session"),
                outputs=[activity, start_btn],
                queue=False,
                show_progress="hidden",
            )
            start_run.failure(
                lambda: restore_activity_button("Begin Session"),
                outputs=[activity, start_btn], queue=False, show_progress="hidden",
            )

            resume_prepare = resume_btn.click(
                lambda: begin_activity("Restoring and verifying the checkpoint…", "Restoring…"),
                outputs=[activity, resume_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            resume_run = resume_prepare.then(
                resume_session_callback,
                inputs=[resume_code],
                outputs=outputs,
                show_progress="hidden",
                trigger_mode="once",
            )
            resume_run.then(
                lambda: restore_activity_button("Resume Session"),
                outputs=[activity, resume_btn],
                queue=False,
                show_progress="hidden",
            )
            resume_run.failure(
                lambda: restore_activity_button("Resume Session"),
                outputs=[activity, resume_btn], queue=False, show_progress="hidden",
            )

            export_bank_btn.click(
                export_generated_bank_callback,
                outputs=[bank_backup_file, bank_backup_status, bank_status],
                show_progress="minimal",
                trigger_mode="once",
            ).then(
                lambda: gr.update(visible=True),
                outputs=[bank_backup_file],
                queue=False,
                show_progress="hidden",
            )

            import_bank_btn.click(
                import_generated_bank_callback,
                inputs=[bank_import_file],
                outputs=[bank_backup_status, bank_status],
                show_progress="minimal",
                trigger_mode="once",
            )

            for index, radio in enumerate(answer_radios):
                radio.change(
                    lambda st, bd, value, slot=index: answer_changed_callback(st, bd, value, slot),
                    inputs=[state, bundle_state, radio],
                    outputs=[state],
                    queue=False,
                )

            play_prepare = play_btn.click(
                lambda: begin_activity("Preparing validated audio playback…", "Preparing Audio…"),
                outputs=[activity, play_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            play_run = play_prepare.then(
                play_audio_callback,
                inputs=[state, bundle_state],
                outputs=[state, audio_html, play_btn, status],
                show_progress="hidden",
                trigger_mode="once",
            )
            play_run.then(end_activity, outputs=[activity], queue=False, show_progress="hidden")
            play_run.failure(
                lambda: restore_activity_button("Play / Replay Audio"),
                outputs=[activity, play_btn], queue=False, show_progress="hidden",
            )

            hint_prepare = hint_btn.click(
                lambda: begin_activity("Preparing strategy hints…", "Loading Hints…"),
                outputs=[activity, hint_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            hint_run = hint_prepare.then(
                show_hints_callback,
                inputs=[state, bundle_state],
                outputs=[hint_output],
                show_progress="hidden",
            )
            hint_run.then(
                lambda: restore_activity_button("Show Strategy Hints"),
                outputs=[activity, hint_btn],
                queue=False,
                show_progress="hidden",
            )
            hint_run.failure(
                lambda: restore_activity_button("Show Strategy Hints"),
                outputs=[activity, hint_btn], queue=False, show_progress="hidden",
            )

            submit_prepare = submit_btn.click(
                lambda: begin_activity("Submitting this passage, updating ability, and saving progress…", "Submitting…"),
                outputs=[activity, submit_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            submit_run = submit_prepare.then(
                submit_passage_callback,
                inputs=[state, bundle_state, nonce_state, *answer_radios],
                outputs=outputs,
                show_progress="hidden",
                trigger_mode="once",
            )
            submit_run.then(end_activity, outputs=[activity], queue=False, show_progress="hidden")
            submit_run.failure(
                lambda: restore_activity_button("Submit Passage"),
                outputs=[activity, submit_btn], queue=False, show_progress="hidden",
            )

            stop_prepare = stop_training_btn.click(
                lambda: begin_activity("Building the partial training report and exports…", "Building Report…"),
                outputs=[activity, stop_training_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            stop_run = stop_prepare.then(
                stop_training_callback,
                inputs=[state],
                outputs=outputs,
                show_progress="hidden",
            )
            stop_run.then(
                lambda: restore_activity_button("Stop Training & Show Partial Report"),
                outputs=[activity, stop_training_btn],
                queue=False,
                show_progress="hidden",
            )
            stop_run.failure(
                lambda: restore_activity_button("Stop Training & Show Partial Report"),
                outputs=[activity, stop_training_btn], queue=False, show_progress="hidden",
            )

            abandon_prepare = abandon_btn.click(
                lambda: begin_activity("Processing the strict-session abandon request…", "Processing…"),
                outputs=[activity, abandon_btn],
                queue=False,
                show_progress="hidden",
                trigger_mode="once",
            )
            abandon_run = abandon_prepare.then(
                abandon_strict_callback,
                inputs=[state, confirm_abandon],
                outputs=outputs,
                show_progress="hidden",
            )
            abandon_run.then(
                lambda: restore_activity_button("Abandon Diagnostic / Simulation"),
                outputs=[activity, abandon_btn],
                queue=False,
                show_progress="hidden",
            )
            abandon_run.failure(
                lambda: restore_activity_button("Abandon Diagnostic / Simulation"),
                outputs=[activity, abandon_btn], queue=False, show_progress="hidden",
            )

        demo.queue(default_concurrency_limit=QUEUE_CONCURRENCY_LIMIT, max_size=32)
    return demo
