from __future__ import annotations

import html
import logging
import time
from pathlib import Path
from uuid import uuid4

import gradio as gr

from core.adaptive import clamp_ilr
from core.audio import AudioError, controlled_audio_html, generate_cached_tts, generate_dialogue_cached_tts, resolve_audio_path
from core.bank_persistence import GeneratedBankPersistence
from core.config import get_settings
from core.constants import (
    DIAGNOSTIC_LENGTHS,
    DISCLAIMER,
    ILR_LEVELS,
    MODE_LABELS,
    QUESTION_TYPES,
    SIMULATION_MODE_LABEL,
    SIMULATION_LENGTHS,
    SKILL_LABELS,
    TRAINING_LENGTHS,
)
from core.generation import LiveGenerationService, ProviderError, _natural_voice_profile
from core.item_bank import ItemBank, shuffled_bundle
from core.languages import (
    LANGUAGE_LABEL_TO_CODE,
    LANGUAGES,
    language_profile,
    voice_choices,
    voice_for_label,
)
from core.models import PassageItem, QuestionItem, SessionState, UserHistory
from core.reporting import build_exports, build_full_report
from core.scoring import item_level_label
from core.session import (
    PassageBundle,
    SessionFlowError,
    activate_bundle,
    advance_skill_or_finish,
    create_session,
    ensure_not_expired,
    mark_listening_play,
    record_answer_change,
    remaining_seconds,
    select_next_bundle,
    skill_is_complete,
    submit_current_bundle,
    update_history,
)
from core.storage import LocalStorage, StorageError

LOGGER = logging.getLogger("dlpt.genai")

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = get_settings()
SETTINGS.ensure_directories(ROOT)
STARTER_BANK_PATH = SETTINGS.starter_bank_runtime_path(ROOT)
MANDARIN_STARTER_BANK_PATH = SETTINGS.mandarin_starter_bank_runtime_path(ROOT)
GENERATED_BANK_PATH = SETTINGS.generated_bank_runtime_path(ROOT)
BANK_PERSISTENCE = GeneratedBankPersistence(SETTINGS, ROOT)
BANK_BOOTSTRAP_MESSAGE = BANK_PERSISTENCE.bootstrap()
BANK = ItemBank(
    [STARTER_BANK_PATH, MANDARIN_STARTER_BANK_PATH, GENERATED_BANK_PATH],
    writable_path=GENERATED_BANK_PATH,
    on_commit=BANK_PERSISTENCE.after_local_commit,
).load()
BANK_STATUS_MESSAGE = BANK_PERSISTENCE.status_text()


def _coverage_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{level}: {count}" for level, count in counts.items() if count) or "none"


def _skill_bank_line(skill: str, health: dict) -> str:
    data = health[skill]
    label = skill.title()
    coverage = _coverage_text(data["ready_ilr_question_counts"])
    if skill == "listening":
        return (
            f"### {label} bank\n"
            f"- **Built-in validated starter:** {data['starter_passages']} passages / "
            f"{data['starter_questions']} questions.\n"
            f"- **Saved AI-generated:** {data['saved_ai_passages']} passages / "
            f"{data['saved_ai_questions']} questions / {data['saved_ai_audio_assets']} audio files.\n"
            f"- **Ready to use now (starter + saved AI):** {data['ready_passages']} passages / "
            f"{data['ready_questions']} questions / {data['ready_audio_assets']} playable audio files.\n"
            f"- **Unavailable because audio is missing or invalid:** {data['missing_or_invalid_audio']} passages.\n"
            f"- **Ready-to-use ILR coverage:** {coverage}."
        )
    return (
        f"### {label} bank\n"
        f"- **Built-in validated starter:** {data['starter_passages']} passages / "
        f"{data['starter_questions']} questions.\n"
        f"- **Saved AI-generated:** {data['saved_ai_passages']} passages / "
        f"{data['saved_ai_questions']} questions.\n"
        f"- **Ready to use now (starter + saved AI):** {data['ready_passages']} passages / "
        f"{data['ready_questions']} questions.\n"
        f"- **Ready-to-use ILR coverage:** {coverage}."
    )


def bank_status_markdown() -> str:
    text = BANK_PERSISTENCE.status_text()
    all_health = BANK.health_summary()
    warning = (
        f" · overlay warnings: {all_health['load_warnings']}"
        if all_health["load_warnings"]
        else ""
    )
    relation_note = (
        f" · cross-skill related pairs tracked: {all_health['cross_skill_related_pairs']}"
        if all_health["cross_skill_related_pairs"]
        else ""
    )
    return (
        f"💾 **Saved AI-generated bank status:** {text}{warning}{relation_note}\n\n"
        "**Bank-write rule:** choosing **Validated bank only**, opening a passage, answering it, or "
        "replaying audio does **not** add anything to the saved AI bank. Only an accepted Fresh-AI "
        "bundle or an explicit backup import/merge can add records.\n\n"
        + "\n\n".join(
            f"## {profile.label}\n\n{_skill_bank_line('reading', BANK.health_summary(code))}\n\n"
            f"{_skill_bank_line('listening', BANK.health_summary(code))}"
            for code, profile in LANGUAGES.items()
        )
    )
SESSION_DIR = SETTINGS.session_runtime_path(ROOT)
HISTORY_DIR = SETTINGS.history_runtime_path(ROOT)
STORAGE = LocalStorage(SESSION_DIR, HISTORY_DIR)
EXPORT_DIR = SETTINGS.runtime_path(Path("storage/exports"), ROOT, "exports")
GENERATOR = LiveGenerationService(SETTINGS, BANK, ROOT)
PROVIDER_READY, PROVIDER_MESSAGE = SETTINGS.provider_readiness()
TOPICS_BY_SKILL = {
    "reading": BANK.topics_for_skill("reading"),
    "listening": BANK.topics_for_skill("listening"),
}
TOPICS = sorted(set(TOPICS_BY_SKILL["reading"]) | set(TOPICS_BY_SKILL["listening"]))
CONTENT_SOURCE_CHOICES = [
    "Validated bank only — fastest",
    "Fresh AI preferred — validate, save to bank, then fall back automatically",
]

QUEUE_CONCURRENCY_LIMIT = SETTINGS.queue_concurrency_limit
MAX_SLOTS = 5


def topic_controls(skill_label: str, language_label: str = "Russian", current_topics=None):
    """Expose only topics that are currently indexed for the selected skill."""
    language: str | None
    if not isinstance(language_label, str):
        # Backward compatibility with the prior two-argument callback.
        current_topics = language_label
        language = None
    else:
        language = LANGUAGE_LABEL_TO_CODE.get(language_label, "ru")
    skills = SKILL_LABELS.get(skill_label, ["reading"])
    choices = sorted({topic for skill in skills for topic in BANK.topics_for_skill(skill, language)})
    current = [] if current_topics in (None, "") else ([current_topics] if isinstance(current_topics, str) else list(current_topics))
    retained = [topic for topic in current if topic in choices]
    return gr.update(choices=choices, value=retained)


def sync_generated_bank_callback():
    """Retry/verify remote bank persistence and expose the real failure reason."""

    try:
        result = BANK_PERSISTENCE.sync_now()
        return (
            gr.update(
                value=(
                    f"✅ Durable bank synchronization succeeded: {result.passage_count} passages / "
                    f"{result.question_count} questions are restart-safe in `{BANK_PERSISTENCE.resolved_repo_id}`."
                ),
                visible=True,
            ),
            bank_status_markdown(),
        )
    except Exception as exc:
        return (
            gr.update(
                value=(
                    "❌ Durable bank synchronization failed. The current container copy is temporary. "
                    f"{html.escape(str(exc))}"
                ),
                visible=True,
            ),
            bank_status_markdown(),
        )


def export_generated_bank_callback():
    """Create a user-downloadable bank+audio backup without mutating the bank."""

    try:
        path = BANK_PERSISTENCE.export_backup(EXPORT_DIR)
        return (
            str(path),
            gr.update(
                value=(
                    "✅ Generated-bank backup created. Keep this ZIP before updating or restarting an "
                    "ephemeral Space. It contains the JSONL bank, manifest, and generated Listening audio."
                ),
                visible=True,
            ),
            bank_status_markdown(),
        )
    except Exception as exc:
        return (
            None,
            gr.update(value=f"❌ Could not create the bank backup: {html.escape(str(exc))}", visible=True),
            bank_status_markdown(),
        )


def import_generated_bank_callback(uploaded_file):
    """Merge a portable backup and reload the shared in-memory bank in place."""

    if not uploaded_file:
        return (
            gr.update(value="Select a generated-bank ZIP or JSONL file first.", visible=True),
            bank_status_markdown(),
        )
    source = getattr(uploaded_file, "name", uploaded_file)
    try:
        result = BANK_PERSISTENCE.import_backup(source)
        BANK.reload()
        return (
            gr.update(
                value=(
                    f"✅ Backup merged successfully: {result.passage_count} generated passages / "
                    f"{result.question_count} questions are now indexed. {result.note}"
                ),
                visible=True,
            ),
            bank_status_markdown(),
        )
    except Exception as exc:
        return (
            gr.update(value=f"❌ Backup import failed safely: {html.escape(str(exc))}", visible=True),
            bank_status_markdown(),
        )


def activity_html(message: str) -> str:
    safe = html.escape(message)
    return (
        "<div class='operation-activity' role='status' aria-live='assertive' aria-busy='true'>"
        "<span class='operation-spinner' aria-hidden='true'></span>"
        f"<span><strong>{safe}</strong><br><small>Please wait. Do not press the button again.</small></span>"
        "</div>"
    )


def begin_activity(message: str, busy_button_label: str):
    return (
        gr.update(value=activity_html(message), visible=True),
        gr.update(value=busy_button_label, interactive=False),
    )


def end_activity():
    return gr.update(value="", visible=False)


def _progress(progress, value: float, description: str) -> None:
    try:
        if progress is not None:
            progress(value, desc=description)
    except Exception:
        # Progress UI is supplementary and must never break assessment flow.
        pass


def restore_activity_button(label: str):
    return gr.update(value="", visible=False), gr.update(value=label, interactive=True)


def mode_controls(mode_label: str, skill_label: str, language_label: str = "Russian"):
    mode = MODE_LABELS[mode_label]
    language = LANGUAGE_LABEL_TO_CODE.get(language_label, "ru")
    voices = voice_choices(language)
    listening_selected = skill_label != "Reading"
    if mode == "training":
        return (
            gr.update(choices=list(TRAINING_LENGTHS), value="Standard — 16 questions", label="Session length"),
            gr.update(choices=["Off", "Standard count-up", "Strict countdown"], value="Off", interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=listening_selected, interactive=listening_selected),
            gr.update(choices=voices, value=language_profile(language).starter_voice_label, visible=listening_selected, interactive=listening_selected),
            gr.update(visible=listening_selected, interactive=listening_selected),
            gr.update(choices=["After each passage", "End of session"], value="After each passage", visible=True),
            gr.update(value="Use selected starting ILR band", visible=False),
            gr.update(value="0", visible=True, interactive=True),
            gr.update(value="3", visible=True, interactive=True),
            gr.update(visible=True, interactive=True, label="Approximate starting ILR band"),
            gr.update(visible=True, interactive=True, label="Target ILR band"),
        )
    if mode == "diagnostic":
        return (
            gr.update(choices=list(DIAGNOSTIC_LENGTHS), value="Efficient — 12 to 20 questions per skill", label="Diagnostic length"),
            gr.update(choices=["Off", "Standard count-up", "Strict countdown"], value="Standard count-up", interactive=True),
            gr.update(visible=False, value=False),
            gr.update(visible=False, value=True),
            gr.update(choices=voices, value=language_profile(language).starter_voice_label, visible=False),
            gr.update(visible=False),
            gr.update(choices=["End of session"], value="End of session", visible=False),
            gr.update(value="Medium difficulty (recommended)", visible=True, interactive=True),
            gr.update(value="0", visible=True, interactive=True),
            gr.update(value="3", visible=True, interactive=True),
            gr.update(visible=True, interactive=True, label="Optional selected diagnostic starting band"),
            gr.update(value="2", visible=False, interactive=False),
        )
    return (
        gr.update(
            choices=list(SIMULATION_LENGTHS),
            value="Standard practice — 35 questions per skill / up to 3 hours",
            label="Simulation length",
        ),
        gr.update(choices=["Strict countdown"], value="Strict countdown", interactive=False),
        gr.update(visible=False, value=False),
        gr.update(visible=False, value=True),
        gr.update(choices=voices, value=language_profile(language).starter_voice_label, visible=False),
        gr.update(visible=False),
        gr.update(choices=["End of session"], value="End of session", visible=False),
        gr.update(value="Medium difficulty (recommended)", visible=False, interactive=False),
        gr.update(value="0", visible=False, interactive=False),
        gr.update(value="3", visible=False, interactive=False),
        gr.update(value="1+", visible=False, interactive=False),
        gr.update(value="2", visible=False, interactive=False),
    )


def _bundle_to_dict(bundle: PassageBundle) -> dict:
    return {
        "passage": bundle.passage.model_dump(mode="json"),
        "questions": [question.model_dump(mode="json") for question in bundle.questions],
    }


def _bundle_from_dict(data: dict | None) -> PassageBundle | None:
    if not data:
        return None
    return PassageBundle(
        passage=PassageItem.model_validate(data["passage"]),
        questions=[QuestionItem.model_validate(item) for item in data["questions"]],
    )


def _history_for(state: SessionState | None) -> UserHistory | None:
    if not state or not state.profile_id or not SETTINGS.enable_history:
        return None
    try:
        return STORAGE.load_history(f"{state.profile_id}__{state.language}")
    except StorageError:
        return UserHistory(profile_id=f"{state.profile_id}__{state.language}", language=state.language)


def _desired_generation_level(state: SessionState) -> str:
    estimate = state.ability_for(state.active_skill)
    return clamp_ilr(estimate.routing_ilr, state.minimum_ilr, state.maximum_ilr)


def _pause_timer_for_loading(state: SessionState, elapsed: float) -> None:
    if elapsed <= 0:
        return
    if state.skill_started_at_epoch is not None:
        state.skill_started_at_epoch += elapsed
    if state.skill_deadline_epoch is not None:
        state.skill_deadline_epoch += elapsed


def _bank_bundle(state: SessionState) -> PassageBundle:
    history = _history_for(state)
    try:
        bundle = select_next_bundle(state, BANK, history)
    except LookupError:
        # Controlled profile-history reuse only after the currently available bank is exhausted.
        bundle = select_next_bundle(state, BANK, None)
    origin = BANK.origin_for(bundle.passage.id)
    state.last_content_source = "generated_bank" if origin == "generated_bank" else "starter_bank"
    if not state.last_content_note:
        source_label = (
            "a previously saved and validated AI-generated item"
            if state.last_content_source == "generated_bank"
            else "a built-in validated starter item"
        )
        if state.content_source == "bank_only":
            state.last_content_note = (
                f"Bank-only selection loaded {source_label}. No new passage was generated and no record "
                "was written to the saved AI-generated bank."
            )
        else:
            state.last_content_note = f"Loaded {source_label}."
    return bundle


def _select_with_safe_history(state: SessionState, progress=None) -> PassageBundle:
    state.last_content_note = None
    _progress(progress, 0.18, "Checking content source and reusable bank…")
    if state.content_source == "fresh_ai_preferred":
        ready, readiness_message = SETTINGS.provider_readiness()
        if not ready:
            state.bank_fallback_count += 1
            state.last_content_note = f"Fresh AI was requested but unavailable: {readiness_message} Bank fallback loaded immediately."
        elif state.generation_requests >= SETTINGS.max_generation_requests_per_session:
            state.bank_fallback_count += 1
            state.last_content_note = (
                f"The per-session live-generation limit ({SETTINGS.max_generation_requests_per_session}) was reached. "
                "A validated bank item was loaded instead."
            )
        else:
            state.generation_requests += 1
            started = time.time()
            try:
                _progress(progress, 0.28, f"Authoring a new {language_profile(state.language).short_label} passage…")
                remaining = max(1, state.max_questions_per_skill - state.completed_count(state.active_skill))
                generated = GENERATOR.generate_and_store(
                    skill=state.active_skill,
                    level=_desired_generation_level(state),
                    mode=state.mode,
                    topics=state.topics,
                    competencies=state.competencies,
                    maximum_questions=min(remaining, 5 if state.active_skill == "reading" else 3),
                    language=state.language,
                )
                _progress(progress, 0.82, "Accepted item validated; updating the reusable bank…")
                questions = shuffled_bundle(
                    generated.questions,
                    seed=f"{state.session_id}:{generated.passage.id}",
                )
                bundle = activate_bundle(state, generated.passage, questions)
                state.generated_passage_ids.append(generated.passage.id)
                state.generation_api_calls += generated.request_count
                state.generation_repair_count += generated.repair_count
                state.last_content_source = "fresh_ai"
                verifier_note = (
                    f" Verification used {generated.verifier_provider}/{generated.verifier_model}."
                    if generated.verifier_provider and generated.verifier_model
                    else ""
                )
                persistence_note = generated.bank_persistence_note or (
                    "The accepted bundle was atomically saved and indexed in the reusable generated-item bank."
                )
                state.last_content_note = (
                    f"Fresh content was authored with {generated.provider_name}/{generated.model_name}, "
                    f"independently audited and blind-verified in {generated.request_count} provider call(s), "
                    f"with {generated.repair_count} repair pass(es).{verifier_note} "
                    f"Choices were shuffled in Python. {persistence_note}"
                )
                LOGGER.info(
                    "Fresh bundle accepted session=%s skill=%s passage=%s provider=%s model=%s questions=%s",
                    state.session_id, state.active_skill, generated.passage.id, generated.provider_name,
                    generated.model_name, len(generated.questions),
                )
                _progress(progress, 0.94, "Fresh item saved and ready…")
                return bundle
            except Exception as exc:
                state.generation_failures += 1
                state.generation_api_calls += int(getattr(exc, "request_count", 0) or 0)
                state.generation_repair_count += int(getattr(exc, "repair_count", 0) or 0)
                state.bank_fallback_count += 1
                # Keep diagnostic detail in server logs/quarantine, not in the
                # learner UI. A rejected AI draft is a recovered content event,
                # not a learner/session error.
                state.last_error = None
                LOGGER.warning(
                    "Fresh generation failed; using bank fallback session=%s skill=%s error_type=%s reason=%s",
                    state.session_id, state.active_skill, type(exc).__name__, str(exc)[:500],
                )
                pipeline_stage = str(getattr(exc, "pipeline_stage", "") or "").strip()
                if pipeline_stage == "question_validation" and state.active_skill == "listening":
                    stage_note = "Question validation failed before audio creation"
                elif pipeline_stage == "audio_generation":
                    stage_note = "Listening audio generation failed after the passage and questions were validated"
                elif pipeline_stage == "audio_validation":
                    stage_note = "Generated Listening audio failed file or duration validation"
                elif pipeline_stage:
                    stage_note = pipeline_stage.replace("_", " ").capitalize()
                else:
                    stage_note = "Fresh generation did not produce an operational item"
                state.last_content_note = (
                    f"{stage_note}. The rejected draft was not used; your session continued "
                    "automatically with a validated saved item."
                )
            finally:
                _pause_timer_for_loading(state, time.time() - started)
    _progress(progress, 0.72, "Selecting a validated bank passage…")
    return _bank_bundle(state)


def _rebuild_current_bundle(state: SessionState) -> PassageBundle:
    if not state.current_passage_id:
        return _select_with_safe_history(state)
    passage = BANK.get_passage(state.current_passage_id)
    questions = shuffled_bundle(BANK.get_questions(passage.id), seed=f"{state.session_id}:{passage.id}")
    questions = [question for question in questions if question.id in state.current_question_ids]
    return PassageBundle(passage=passage, questions=questions)


def _timer_html(state: SessionState) -> str:
    if state.timer_mode == "off":
        return ""
    element_id = f"timer_{state.session_id}_{state.active_skill}"
    if state.timer_mode == "standard":
        start_ms = int((state.skill_started_at_epoch or time.time()) * 1000)
        return f"""
<div class='timer-card' id='{element_id}' aria-live='polite'>Elapsed: 00:00:00</div>
<script>
(() => {{ const el=document.getElementById('{element_id}'); const start={start_ms};
const draw=()=>{{const s=Math.max(0,Math.floor((Date.now()-start)/1000));const h=String(Math.floor(s/3600)).padStart(2,'0');const m=String(Math.floor((s%3600)/60)).padStart(2,'0');const x=String(s%60).padStart(2,'0');if(el)el.textContent=`Elapsed: ${{h}}:${{m}}:${{x}}`;}};draw();setInterval(draw,1000); }})();
</script>"""
    deadline_ms = int((state.skill_deadline_epoch or time.time()) * 1000)
    return f"""
<div class='timer-card strict' id='{element_id}' role='status' aria-live='off'>Remaining: --:--:--</div>
<script>
(() => {{ const el=document.getElementById('{element_id}'); const deadline={deadline_ms};
let timerId=null;
const expire=()=>{{
  if(!el || el.dataset.expirySent==='true') return;
  el.dataset.expirySent='true';
  const host=document.getElementById('timer-expired-trigger');
  const button=host && (host.querySelector('button') || (host.tagName==='BUTTON' ? host : null));
  if(button) button.click();
}};
const draw=()=>{{const s=Math.max(0,Math.floor((deadline-Date.now())/1000));const h=String(Math.floor(s/3600)).padStart(2,'0');const m=String(Math.floor((s%3600)/60)).padStart(2,'0');const x=String(s%60).padStart(2,'0');if(el)el.textContent=`Remaining: ${{h}}:${{m}}:${{x}}`;if(s<=0){{if(timerId)clearInterval(timerId);expire();}}}};draw();if(deadline>Date.now())timerId=setInterval(draw,1000); }})();
</script>"""


def _status_text(state: SessionState, extra: str = "") -> str:
    completed = state.completed_count(state.active_skill)
    mode_name = {"training": "Training Mode", "diagnostic": "Adaptive Diagnostic", "simulation": SIMULATION_MODE_LABEL}[state.mode]
    lines = [
        f"### {mode_name} — {state.active_skill.title()}",
        f"**Progress:** {completed}/{state.max_questions_per_skill} questions in this skill  |  **Session code:** `{state.session_id}`",
    ]
    if state.mode == "training":
        estimate = state.ability_for(state.active_skill)
        lines.append(
            f"**Adaptive routing:** next passage is targeted at **ILR {estimate.routing_ilr}** "
            f"within the configured {state.minimum_ilr}–{state.maximum_ilr} range."
        )
        if estimate.practice_ilr:
            lines.append(f"Current provisional practice band: **ILR {estimate.practice_ilr}** ({estimate.confidence} confidence).")
    elif state.shortened_simulation:
        lines.append("**Shortened simulation:** this is not equivalent to a complete test.")
    else:
        lines.append("Adaptive calculations are hidden during strict testing conditions.")
    if state.mode in {"training", "diagnostic"}:
        lines.append(f"**Eligible item range:** ILR {state.minimum_ilr} through ILR {state.maximum_ilr}.")
    health = BANK.health_summary(state.language)
    skill_health = health[state.active_skill]
    if state.content_source == "fresh_ai_preferred":
        audio_note = (
            f" / {skill_health['saved_ai_audio_assets']} audio assets"
            if state.active_skill == "listening"
            else ""
        )
        lines.append(
            f"**Content:** Fresh AI preferred · generated this session: {len(state.generated_passage_ids)} · "
            f"bank fallbacks: {state.bank_fallback_count} · saved AI-generated {state.active_skill.title()} bank: "
            f"{skill_health['saved_ai_passages']} passages / {skill_health['saved_ai_questions']} questions{audio_note}."
        )
    else:
        lines.append(
            f"**Content:** Validated bank only · selected from {skill_health['ready_passages']} ready-to-use "
            f"{state.active_skill.title()} passages ({skill_health['starter_passages']} built-in starter + "
            f"{skill_health['saved_ai_passages']} saved AI-generated). **This session does not write new bank records.**"
        )
    if state.last_content_source == "fresh_ai":
        lines.append("✅ **Fresh AI bundle generated, validated, saved to the reusable bank, and selected for this passage.**")
    elif state.content_source == "fresh_ai_preferred" and state.last_content_source in {"starter_bank", "generated_bank"}:
        lines.append("⚠️ **Fresh AI fallback:** a validated bank item was selected because live generation was unavailable or rejected.")
    if state.last_content_note:
        lines.append(f"> {state.last_content_note}")
    if extra:
        lines.append(extra)
    return "\n\n".join(lines)


def _passage_markdown(bundle: PassageBundle, state: SessionState) -> str:
    passage = bundle.passage
    if passage.skill == "reading":
        return f"### {language_profile(passage.language).short_label} Passage\n\n{passage.passage_ru}"
    source = "Synthetic TTS audio" if passage.source_type == "synthetic" else passage.source_type
    return (
        "### Listening Passage\n\n"
        f"**Audio source:** {source}. The transcript is hidden during the active test.\n\n"
        "Questions remain visible while audio plays. Use the playback button when ready."
    )


def _question_updates(bundle: PassageBundle | None):
    outputs = []
    questions = bundle.questions if bundle else []
    for index in range(MAX_SLOTS):
        if index < len(questions):
            question = questions[index]
            outputs.append(gr.update(value=f"**{index + 1}. {question.stem_en}**", visible=True))
            choices = [(f"{letter}. {question.choices[letter]}", letter) for letter in ["A", "B", "C", "D"]]
            outputs.append(gr.update(choices=choices, value=None, visible=True, interactive=True, label=f"Question {index + 1}"))
        else:
            outputs.append(gr.update(value="", visible=False))
            outputs.append(gr.update(value=None, visible=False, interactive=False))
    return outputs


def _blank_questions():
    outputs = []
    for _ in range(MAX_SLOTS):
        outputs.append(gr.update(value="", visible=False))
        outputs.append(gr.update(value=None, visible=False, interactive=False))
    return outputs


def _test_render(state: SessionState, bundle: PassageBundle, message: str = ""):
    passage = bundle.passage
    strict_listening = passage.skill == "listening" and state.mode in {"diagnostic", "simulation"}
    play_label = "Play Audio Once" if strict_listening else "Play / Replay Audio"
    play_visible = passage.skill == "listening"
    return [
        state,
        _bundle_to_dict(bundle),
        uuid4().hex,
        gr.update(value=_status_text(state, message), visible=True),
        gr.update(value=_timer_html(state), visible=state.timer_mode != "off"),
        gr.update(value=f"### Context\n\n{passage.orientation_en}", visible=True),
        gr.update(value=_passage_markdown(bundle, state), visible=True),
        gr.update(value=("Synthetic TTS practice audio. Starter audio is cached in the repository." if play_visible else ""), visible=play_visible),
        gr.update(value=play_label, visible=play_visible, interactive=play_visible),
        gr.update(value="", visible=play_visible),
        *_question_updates(bundle),
        gr.update(visible=state.mode == "training" and state.hints_enabled, interactive=True),
        gr.update(value="", visible=False),
        gr.update(value="Submit Passage", visible=True, interactive=True),
        gr.update(visible=state.mode == "training"),
        gr.update(visible=state.mode in {"diagnostic", "simulation"}),
        gr.update(visible=state.mode in {"diagnostic", "simulation"}, value=False),
        gr.update(value="", visible=False),
        gr.update(value="", visible=False),
        gr.update(value=None, visible=False),
        gr.update(value=None, visible=False),
        gr.update(value=bank_status_markdown(), visible=True),
    ]


def _inactive_render(state: SessionState | None, status: str, report: str = "", json_path: str | None = None, csv_path: str | None = None):
    return [
        state,
        None,
        None,
        gr.update(value=status, visible=True),
        gr.update(value="", visible=False),
        gr.update(value="", visible=False),
        gr.update(value="", visible=False),
        gr.update(value="", visible=False),
        gr.update(visible=False, interactive=False),
        gr.update(value="", visible=False),
        *_blank_questions(),
        gr.update(visible=False),
        gr.update(value="", visible=False),
        gr.update(visible=False, interactive=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False, value=False),
        gr.update(value="", visible=False),
        gr.update(value=report, visible=bool(report)),
        gr.update(value=json_path, visible=bool(json_path)),
        gr.update(value=csv_path, visible=bool(csv_path)),
        gr.update(value=bank_status_markdown(), visible=True),
    ]


def _length_settings(mode: str, label: str) -> tuple[int, int, bool, bool, int | None]:
    if mode == "training":
        max_q = TRAINING_LENGTHS[label]
        return max_q, max_q, False, False, None
    if mode == "diagnostic":
        max_q = DIAGNOSTIC_LENGTHS[label]
        minimum = 12 if label.startswith("Efficient") else 16
        return max_q, minimum, False, False, None
    legacy_lengths = {
        "Shortened — 12 questions per skill (not a full simulation)": 12,
        "Standard — 35 questions per skill": 35,
        # Old clients may still post this retired label; normalize it to the
        # supported 35-question standard rather than preserving the old promise.
        "Full-length — minimum 35, up to 60 questions / 3 hours per skill": 35,
    }
    max_q = SIMULATION_LENGTHS.get(label, legacy_lengths.get(label))
    if max_q is None:
        raise ValueError(f"Unknown simulation length: {label}")
    shortened = max_q < 35
    full = max_q >= 35
    seconds = 1800 if shortened else 10800
    return max_q, max_q, full, shortened, seconds


def expire_section_callback(
    state: SessionState | None,
    bundle_data: dict | None,
    nonce: str | None,
):
    """End an expired section without waiting for another learner action."""

    if not state or state.status not in {"active", "expired"} or state.skill_deadline_epoch is None:
        return _inactive_render(state, "### No active strict timer")
    # Older checkpoints may carry the former section-level ``expired`` status.
    # Expiry is now handled as a section transition, so recover that state and
    # continue into the next selected skill when applicable.
    state.status = "active"
    now = time.time()
    if remaining_seconds(state, now) > 0:
        bundle = _bundle_from_dict(bundle_data)
        if bundle:
            return _test_render(state, bundle, "An early timer event was ignored; the section remains active.")
        return _inactive_render(state, "### Timer event ignored safely")

    bundle = _bundle_from_dict(bundle_data)
    auto_submitted = False
    if bundle and bundle.passage.id == state.current_passage_id:
        all_answered = all(state.current_answers.get(question.id) for question in bundle.questions)
        all_before_deadline = all(
            state.current_answer_timestamps.get(question.id, float("inf")) <= state.skill_deadline_epoch
            for question in bundle.questions
        )
        if all_answered and all_before_deadline:
            records = submit_current_bundle(
                state,
                bundle.passage,
                bundle.questions,
                dict(state.current_answers),
                nonce or f"expiry-{uuid4().hex}",
                now=state.skill_deadline_epoch,
                enforce_deadline=False,
            )
            auto_submitted = bool(records)
        else:
            state.current_passage_id = None
            state.current_question_ids = []
            state.current_answers = {}
            state.current_answer_changes = {}
            state.current_answer_timestamps = {}
            state.current_listening_plays = 0

    finished = advance_skill_or_finish(state, now=now, force=True)
    note = (
        "The fully answered active passage was submitted before the section closed."
        if auto_submitted
        else "The incomplete active passage was not scored."
    )
    if finished:
        history = _history_for(state)
        if history and state.profile_id:
            STORAGE.save_history(update_history(history, state))
        STORAGE.save_checkpoint(state)
        report = build_full_report(state, BANK)
        json_path, csv_path = build_exports(state, EXPORT_DIR)
        return _inactive_render(
            state,
            f"### Time expired — session complete\n\n{note}\n\nCompleted passages remain saved.",
            report,
            json_path,
            csv_path,
        )

    next_bundle = _select_with_safe_history(state)
    STORAGE.save_checkpoint(state)
    return _test_render(
        state,
        next_bundle,
        f"The prior skill section ended automatically when time expired. {note}",
    )


def _normalize_multiselect(value, allowed_values: list[str], field_name: str) -> list[str]:
    """Normalize a Gradio multi-select payload and reject unknown values safely."""

    if value is None or value == "":
        return []
    values = [value] if isinstance(value, str) else list(value)
    invalid = [item for item in values if item not in allowed_values]
    if invalid:
        raise ValueError(f"Invalid {field_name} selection: {', '.join(map(str, invalid))}")
    # Preserve the user's order while removing accidental duplicates.
    return list(dict.fromkeys(values))


def start_session_callback(
    mode_label, skill_label, start_level, target_level, length_label, timer_label,
    topics, competencies, feedback_timing, hints_enabled, transcript_review,
    voice_label, speech_rate_label, profile_id, content_source_label="Validated bank only — fastest",
    adaptive_start_label="Use selected starting ILR band", minimum_ilr="0", maximum_ilr="3",
    language_label="Russian",
    progress=gr.Progress(),
):
    try:
        _progress(progress, 0.04, "Validating session settings…")
        mode = MODE_LABELS[mode_label]
        language = LANGUAGE_LABEL_TO_CODE[language_label]
        skills = SKILL_LABELS[skill_label]
        if mode == "simulation":
            minimum_ilr, maximum_ilr = "0", "3"
            adaptive_start_policy = "medium"
        else:
            if ILR_LEVELS.index(minimum_ilr) > ILR_LEVELS.index(maximum_ilr):
                raise ValueError("The lowest allowed ILR band cannot be higher than the highest allowed band.")
            adaptive_start_policy = "selected" if adaptive_start_label.startswith("Use selected") else "medium"
        if mode == "training" or adaptive_start_policy == "selected":
            if not ILR_LEVELS.index(minimum_ilr) <= ILR_LEVELS.index(start_level) <= ILR_LEVELS.index(maximum_ilr):
                raise ValueError("The selected starting ILR band must fall inside the allowed adaptive range.")
        if mode == "training" and not ILR_LEVELS.index(minimum_ilr) <= ILR_LEVELS.index(target_level) <= ILR_LEVELS.index(maximum_ilr):
            raise ValueError("The Training target ILR band must fall inside the allowed adaptive range.")
        allowed_topics = sorted({topic for selected_skill in skills for topic in BANK.topics_for_skill(selected_skill, language)})
        topics = _normalize_multiselect(topics, allowed_topics, "topic")
        competencies = _normalize_multiselect(competencies, QUESTION_TYPES, "competency")
        max_q, minimum, simulation_full, shortened, simulation_seconds = _length_settings(mode, length_label)
        timer_mode = "off" if timer_label == "Off" else ("standard" if timer_label == "Standard count-up" else "strict")
        if mode == "simulation":
            timer_mode = "strict"
        time_limit = simulation_seconds
        if timer_mode == "strict" and time_limit is None:
            time_limit = max(1200, max_q * 120)
        feedback_mode = "end_of_passage" if mode == "training" and feedback_timing == "After each passage" else "end_only"
        _progress(progress, 0.10, "Creating independent adaptive skill state…")
        state = create_session(
            language=language,
            mode=mode, selected_skills=skills, start_level=start_level, target_level=target_level,
            topics=topics or [], competencies=competencies or [], max_questions_per_skill=max_q,
            minimum_questions_per_skill=minimum, timer_mode=timer_mode,
            time_limit_seconds_per_skill=time_limit, profile_id=profile_id,
            feedback_mode=feedback_mode, hints_enabled=bool(hints_enabled) if mode == "training" else False,
            transcript_review_enabled=bool(transcript_review) if mode == "training" else True,
            replay_allowed=mode == "training", slow_audio_allowed=mode == "training",
            voice_label=voice_label, speech_rate_label=speech_rate_label,
            content_source=("fresh_ai_preferred" if content_source_label.startswith("Fresh AI") else "bank_only"),
            simulation_full=simulation_full, shortened_simulation=shortened,
            adaptive_start_policy=adaptive_start_policy,
            minimum_ilr=minimum_ilr,
            maximum_ilr=maximum_ilr,
        )
        bundle = _select_with_safe_history(state, progress)
        _progress(progress, 0.96, "Saving the initial checkpoint…")
        STORAGE.save_checkpoint(state)
        _progress(progress, 1.0, "Session ready")
        return _test_render(state, bundle, "Progress is checkpointed after every passage; accepted fresh items become reusable bank content.")
    except Exception as exc:
        return _inactive_render(None, f"### Session could not start\n\n{html.escape(str(exc))}\n\nThe app did not clear any prior checkpoint.")


def resume_session_callback(session_code: str, progress=gr.Progress()):
    try:
        _progress(progress, 0.15, "Loading and verifying checkpoint…")
        state = STORAGE.load_checkpoint(session_code.strip())
        if state.status == "completed":
            _progress(progress, 0.78, "Building the final report and exports…")
            report = build_full_report(state, BANK)
            json_path, csv_path = build_exports(state, EXPORT_DIR)
            return _inactive_render(state, "### Completed session restored", report, json_path, csv_path)
        ensure_not_expired(state)
        _progress(progress, 0.65, "Restoring the active passage…")
        bundle = _rebuild_current_bundle(state)
        STORAGE.save_checkpoint(state)
        _progress(progress, 1.0, "Session restored")
        return _test_render(state, bundle, "Session restored from the latest valid checkpoint.")
    except Exception as exc:
        return _inactive_render(None, f"### Recovery failed safely\n\n{html.escape(str(exc))}")


def answer_changed_callback(state: SessionState | None, bundle_data: dict | None, value: str | None, slot: int):
    if not state or not bundle_data or value is None:
        return state
    bundle = _bundle_from_dict(bundle_data)
    if bundle and slot < len(bundle.questions):
        record_answer_change(state, bundle.questions[slot].id, value)
    return state


def play_audio_callback(state: SessionState | None, bundle_data: dict | None, progress=gr.Progress()):
    if not state or not bundle_data:
        return state, gr.update(value="", visible=False), gr.update(), gr.update(value="Start or resume a session first.")
    bundle = _bundle_from_dict(bundle_data)
    if not bundle or bundle.passage.skill != "listening":
        return state, gr.update(value="", visible=False), gr.update(visible=False), gr.update()
    try:
        strict = state.mode in {"diagnostic", "simulation"}
        if strict and state.current_listening_plays >= 1:
            raise SessionFlowError("Replay is disabled in strict listening conditions.")
        _progress(progress, 0.10, "Authorizing browser playback…")
        asset = BANK.get_audio(bundle.passage.audio_asset_id)
        if not asset:
            raise AudioError("No validated audio asset is linked to this passage.")
        _progress(progress, 0.30, "Loading validated audio…")
        path = resolve_audio_path(asset, ROOT)
        audio_note = ""
        starter_label = language_profile(state.language).starter_voice_label

        # Upgrade previously saved AI audio lazily when it is actually selected.
        # This avoids the old startup problem where every remote MP3 was restored or
        # regenerated at once, while ensuring classmates hear the new natural-v2
        # rendering even for passages already present in the generated bank.
        if asset.engine.lower() not in {"edge-tts", "edge tts"} or asset.engine_version != "7.2.8-dialogue-v1":
            try:
                _progress(progress, 0.42, "Preparing a native neural voice for this passage…")
                voice, rate, pitch, volume = _natural_voice_profile(bundle.passage, SETTINGS)
                cache_dir = SETTINGS.audio_cache_runtime_path(ROOT)
                path = generate_dialogue_cached_tts(
                    bundle.passage.passage_ru, cache_dir, voice=voice, rate=rate,
                    pitch=pitch, volume=volume, language=bundle.passage.language,
                    engine_version="edge-tts-7.2.8-dialogue-v1",
                    timeout_seconds=SETTINGS.tts_timeout_seconds,
                    synthesizer=generate_cached_tts,
                )
                audio_note = " Native neural speech loaded and cached for this passage."
            except Exception as tts_exc:
                audio_note = f" Natural speech upgrade was unavailable; the existing validated audio was used ({type(tts_exc).__name__})."

        if state.mode == "training" and (state.voice_label != starter_label or state.speech_rate_label != "Normal"):
            rate_map = {"Very slow": "-25%", "Slow": "-15%", "Normal": "+0%", "Fast": "+10%"}
            try:
                _progress(progress, 0.48, "Preparing the selected training voice and speed…")
                cache_dir = SETTINGS.audio_cache_runtime_path(ROOT)
                path = generate_dialogue_cached_tts(
                    bundle.passage.passage_ru, cache_dir,
                    voice=voice_for_label(state.language, state.voice_label),
                    rate=rate_map.get(state.speech_rate_label, "+0%"),
                    pitch="+0Hz", volume="+0%", language=bundle.passage.language,
                    engine_version="edge-tts-7.2.8-dialogue-v1-training",
                    timeout_seconds=SETTINGS.tts_timeout_seconds,
                    synthesizer=generate_cached_tts,
                )
                audio_note = " Requested training voice/speed loaded with natural spoken phrasing from the deterministic TTS cache."
            except Exception as tts_exc:
                audio_note = f" Requested training voice/speed was unavailable; cached starter audio was used ({type(tts_exc).__name__})."
        _progress(progress, 0.82, "Preparing browser playback…")
        audio_html = controlled_audio_html(
            str(path),
            f"audio_{state.session_id}_{bundle.passage.id}_{state.current_listening_plays + 1}",
            strict,
        )
        _progress(progress, 1.0, "Audio ready")
        status = _status_text(
            state,
            "Audio is ready. Press the play button inside the audio player. The play is recorded only after the browser confirms that sound started."
            f"{audio_note}",
        )
        return (
            state,
            gr.update(value=audio_html, visible=True),
            # Keep retry available when autoplay is blocked. Browser-confirmed
            # playback disables this button in strict modes.
            gr.update(interactive=True, visible=True),
            gr.update(value=status),
        )
    except Exception as exc:
        state.last_error = str(exc)
        STORAGE.save_checkpoint(state)
        return state, gr.update(value="", visible=False), gr.update(interactive=False), gr.update(value=_status_text(state, f"Recoverable audio error: {html.escape(str(exc))}"))


def confirm_audio_playback_callback(state: SessionState | None, bundle_data: dict | None):
    """Count a Listening play only after the browser emits ``playing``."""

    if not state or not bundle_data:
        return state, gr.update(), gr.update()
    bundle = _bundle_from_dict(bundle_data)
    if (
        not bundle
        or bundle.passage.skill != "listening"
        or bundle.passage.id != state.current_passage_id
    ):
        return state, gr.update(), gr.update(value=_status_text(state, "A stale playback event was ignored."))
    try:
        mark_listening_play(state)
        STORAGE.save_checkpoint(state)
        strict = state.mode in {"diagnostic", "simulation"}
        label = "Audio Started — Replay Disabled" if strict else "Play / Replay Audio"
        return (
            state,
            gr.update(value=label, visible=True, interactive=not strict),
            gr.update(
                value=_status_text(
                    state,
                    f"Browser-confirmed Listening playback count for this passage: {state.current_listening_plays}.",
                ),
                visible=True,
            ),
        )
    except Exception as exc:
        state.last_error = str(exc)
        STORAGE.save_checkpoint(state)
        return (
            state,
            gr.update(value="Audio Started — Replay Disabled", visible=True, interactive=False),
            gr.update(value=_status_text(state, html.escape(str(exc))), visible=True),
        )


HINTS = {
    "main idea": "Identify the statement that covers the whole passage, not one isolated fact.",
    "prominent detail": "Locate the explicitly stated person, action, time, place, or result.",
    "inference": "Choose only what is strongly supported; do not add outside knowledge.",
    "speaker/writer intent": "Ask what action or belief the writer wants from the audience.",
    "tone or attitude": "Notice contrast words, evaluation, certainty, and emotional distance.",
    "reference": "Trace the noun or idea that a pronoun or phrase points back to.",
    "sequence": "Put the stated events or instructions in their actual order.",
    "cause and effect": "Separate the reason from the result and verify the direction.",
    "relationship of ideas": "Look for contrast, support, qualification, example, or conclusion.",
    "meaning from context": "Use the surrounding clause and discourse role, not a dictionary guess alone.",
}


def show_hints_callback(state: SessionState | None, bundle_data: dict | None):
    if not state or state.mode != "training" or not state.hints_enabled:
        return gr.update(value="Hints are not enabled for this session.", visible=True)
    bundle = _bundle_from_dict(bundle_data)
    if not bundle:
        return gr.update(value="No active passage.", visible=True)
    lines = ["### Strategy Hints"]
    for index, question in enumerate(bundle.questions, start=1):
        lines.append(f"- **Question {index} — {question.question_type}:** {HINTS.get(question.question_type, 'Return to the exact passage evidence.')}")
    return gr.update(value="\n".join(lines), visible=True)


def _passage_feedback(records, passage: PassageItem, state: SessionState) -> str:
    calibration = "provisional" if all(record.provisional_item for record in records) else "mixed provisional/calibrated"
    lines = [
        "### Passage Feedback",
        f"**Passage authoring target:** ILR {passage.target_ilr} ({calibration} item metadata).",
    ]
    for index, record in enumerate(records, start=1):
        mark = "✅ Correct" if record.is_correct else "❌ Incorrect"
        lines.append(f"**{index}. {mark} — {record.stem_en}**")
        lines.append(f"- Item level: **{item_level_label(record)}**")
        lines.append(f"- Correct answer: {record.correct_key}. {record.choices_snapshot[record.correct_key]}")
        lines.append(f"- Explanation: {record.rationale_en}")
        lines.append(f"- {language_profile(record.language).short_label} evidence: `{record.evidence_ru}`")
    if passage.skill == "listening" and records and records[0].mode == "training" and state.transcript_review_enabled:
        lines.append(f"**Transcript review:** {passage.passage_ru}")
    return "\n\n".join(lines)


def submit_passage_callback(state: SessionState | None, bundle_data: dict | None, nonce: str | None, a1, a2, a3, a4, a5, progress=gr.Progress()):
    if not state or not bundle_data or not nonce:
        return _inactive_render(state, "### No active passage\n\nStart or resume a session.")
    bundle = _bundle_from_dict(bundle_data)
    answers_values = [a1, a2, a3, a4, a5]
    answers = {question.id: answers_values[index] for index, question in enumerate(bundle.questions)}
    try:
        _progress(progress, 0.08, "Checking that the passage is complete…")
        if bundle.passage.skill == "listening" and state.mode in {"diagnostic", "simulation"} and state.current_listening_plays < 1:
            raise SessionFlowError("Play the listening passage once before submitting.")
        _progress(progress, 0.22, "Scoring responses and updating the adaptive estimate…")
        records = submit_current_bundle(state, bundle.passage, bundle.questions, answers, nonce)
        if not records:
            current = _rebuild_current_bundle(state)
            return _test_render(state, current, "Duplicate submission ignored; no response was recorded twice.")
        _progress(progress, 0.46, "Saving the completed passage checkpoint…")
        STORAGE.save_checkpoint(state)
        feedback = ""
        if state.mode == "training" and state.feedback_mode == "end_of_passage":
            feedback = _passage_feedback(records, bundle.passage, state)
        finished = False
        if skill_is_complete(state):
            finished = advance_skill_or_finish(state)
        if finished:
            history = _history_for(state)
            if history and state.profile_id:
                STORAGE.save_history(update_history(history, state))
            STORAGE.save_checkpoint(state)
            report = build_full_report(state, BANK)
            json_path, csv_path = build_exports(state, EXPORT_DIR)
            return _inactive_render(
                state,
                f"### Session complete\n\n{DISCLAIMER}\n\nCompleted responses: {len(state.responses)}.",
                report,
                json_path,
                csv_path,
            )
        try:
            next_bundle = _select_with_safe_history(state, progress)
        except LookupError:
            if state.mode == "simulation" and state.completed_count(state.active_skill) >= 35:
                finished = advance_skill_or_finish(state, force=True)
                if finished:
                    history = _history_for(state)
                    if history and state.profile_id:
                        STORAGE.save_history(update_history(history, state))
                    STORAGE.save_checkpoint(state)
                    report = build_full_report(state, BANK)
                    json_path, csv_path = build_exports(state, EXPORT_DIR)
                    return _inactive_render(state, "### Session complete\n\nValidated bank exhausted after the full-simulation minimum was satisfied.", report, json_path, csv_path)
                next_bundle = _select_with_safe_history(state)
            else:
                raise
        _progress(progress, 0.94, "Saving the next-passage checkpoint…")
        STORAGE.save_checkpoint(state)
        _progress(progress, 1.0, "Next passage ready")
        rendered = _test_render(state, next_bundle, "Passage submitted and checkpoint saved.")
        if feedback:
            rendered[26] = gr.update(value=feedback, visible=True)
        return rendered
    except Exception as exc:
        state.last_error = str(exc)
        STORAGE.save_checkpoint(state)
        rendered = _test_render(state, bundle, f"Recoverable submission issue: {html.escape(str(exc))}")
        # Preserve the user's current radio values after a validation error.
        for index, question in enumerate(bundle.questions):
            radio_output_index = 11 + index * 2
            choices = [(f"{letter}. {question.choices[letter]}", letter) for letter in ["A", "B", "C", "D"]]
            rendered[radio_output_index] = gr.update(
                choices=choices, value=answers_values[index], visible=True, interactive=True,
                label=f"Question {index + 1}",
            )
        return rendered


def stop_training_callback(state: SessionState | None):
    if not state or state.mode != "training":
        return _inactive_render(state, "### Only Training Mode can be stopped with a partial review.")
    state.status = "stopped"
    STORAGE.save_checkpoint(state)
    report = build_full_report(state, BANK)
    json_path, csv_path = build_exports(state, EXPORT_DIR)
    return _inactive_render(state, "### Training stopped\n\nA partial practice report was generated from completed passages.", report, json_path, csv_path)


def abandon_strict_callback(state: SessionState | None, confirmed: bool):
    if not state or state.mode not in {"diagnostic", "simulation"}:
        return _inactive_render(state, "### No active strict session to abandon.")
    if not confirmed:
        bundle = _rebuild_current_bundle(state)
        return _test_render(state, bundle, "Check the confirmation box before abandoning this active session.")
    state.status = "stopped"
    STORAGE.save_checkpoint(state)
    json_path, csv_path = build_exports(state, EXPORT_DIR)
    if state.mode == "simulation":
        report = "## Simulation abandoned\n\nDetailed answer review is withheld because the strict simulation was not completed. Completed response data are available in the exports."
    else:
        report = build_full_report(state, BANK)
    return _inactive_render(state, "### Session abandoned after confirmation\n\nCompleted passage data remain checkpointed and exportable.", report, json_path, csv_path)
