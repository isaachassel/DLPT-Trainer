from __future__ import annotations

import html
import logging
import time
from pathlib import Path
from uuid import uuid4

import gradio as gr

from core.audio import AudioError, controlled_audio_html, generate_cached_tts, resolve_audio_path
from core.bank_persistence import GeneratedBankPersistence
from core.config import get_settings
from core.constants import (
    DIAGNOSTIC_LENGTHS,
    DISCLAIMER,
    ILR_LEVELS,
    ILR_THETA,
    MODE_LABELS,
    QUESTION_TYPES,
    SIMULATION_LENGTHS,
    SKILL_LABELS,
    TRAINING_LENGTHS,
)
from core.generation import LiveGenerationService, ProviderError
from core.item_bank import ItemBank, shuffled_bundle
from core.models import PassageItem, QuestionItem, SessionState, UserHistory
from core.reporting import build_exports, build_full_report
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
GENERATED_BANK_PATH = SETTINGS.generated_bank_runtime_path(ROOT)
BANK_PERSISTENCE = GeneratedBankPersistence(SETTINGS, ROOT)
BANK_BOOTSTRAP_MESSAGE = BANK_PERSISTENCE.bootstrap()
BANK = ItemBank(
    [STARTER_BANK_PATH, GENERATED_BANK_PATH],
    writable_path=GENERATED_BANK_PATH,
    on_commit=BANK_PERSISTENCE.after_local_commit,
).load()
BANK_STATUS_MESSAGE = BANK_PERSISTENCE.status_text()


def bank_status_markdown() -> str:
    text = BANK_PERSISTENCE.status_text()
    health = BANK.health_summary()
    warning = (
        f" · overlay warnings: {health['load_warnings']}"
        if health["load_warnings"]
        else ""
    )
    return f"💾 **Reusable bank status:** {text}{warning}"
SESSION_DIR = SETTINGS.session_runtime_path(ROOT)
HISTORY_DIR = SETTINGS.history_runtime_path(ROOT)
STORAGE = LocalStorage(SESSION_DIR, HISTORY_DIR)
EXPORT_DIR = SETTINGS.runtime_path(Path("storage/exports"), ROOT, "exports")
GENERATOR = LiveGenerationService(SETTINGS, BANK, ROOT)
PROVIDER_READY, PROVIDER_MESSAGE = SETTINGS.provider_readiness()
TOPICS = sorted({passage.topic for passage in BANK.passages.values()})
CONTENT_SOURCE_CHOICES = [
    "Validated bank only — fastest",
    "Fresh AI preferred — validate, save to bank, then fall back automatically",
]

QUEUE_CONCURRENCY_LIMIT = SETTINGS.queue_concurrency_limit
MAX_SLOTS = 5


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


def mode_controls(mode_label: str, skill_label: str):
    mode = MODE_LABELS[mode_label]
    listening_selected = skill_label != "Reading"
    if mode == "training":
        return (
            gr.update(choices=list(TRAINING_LENGTHS), value="Standard — 16 questions", label="Session length"),
            gr.update(choices=["Off", "Standard count-up", "Strict countdown"], value="Off", interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=listening_selected, interactive=listening_selected),
            gr.update(visible=listening_selected, interactive=listening_selected),
            gr.update(visible=listening_selected, interactive=listening_selected),
            gr.update(choices=["After each passage", "End of session"], value="After each passage", visible=True),
        )
    if mode == "diagnostic":
        return (
            gr.update(choices=list(DIAGNOSTIC_LENGTHS), value="Efficient — 12 to 20 questions per skill", label="Diagnostic length"),
            gr.update(choices=["Off", "Standard count-up", "Strict countdown"], value="Standard count-up", interactive=True),
            gr.update(visible=False, value=False),
            gr.update(visible=False, value=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(choices=["End of session"], value="End of session", visible=False),
        )
    return (
        gr.update(choices=list(SIMULATION_LENGTHS), value="Standard — 35 questions per skill", label="Simulation length"),
        gr.update(choices=["Strict countdown"], value="Strict countdown", interactive=False),
        gr.update(visible=False, value=False),
        gr.update(visible=False, value=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(choices=["End of session"], value="End of session", visible=False),
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
        return STORAGE.load_history(state.profile_id)
    except StorageError:
        return UserHistory(profile_id=state.profile_id)


def _nearest_ilr(theta: float) -> str:
    return min(ILR_THETA, key=lambda level: abs(ILR_THETA[level] - theta))


def _desired_generation_level(state: SessionState) -> str:
    estimate = state.ability_for(state.active_skill)
    if state.completed_count(state.active_skill) == 0 and state.mode in {"diagnostic", "simulation"}:
        return "2"
    if state.mode == "training":
        target_theta = ILR_THETA.get(state.target_level, estimate.theta)
        return _nearest_ilr(0.65 * estimate.theta + 0.35 * target_theta)
    return _nearest_ilr(estimate.theta)


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
        state.last_content_note = (
            "Loaded a previously validated AI-generated bank item."
            if state.last_content_source == "generated_bank"
            else "Loaded a validated starter-bank item."
        )
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
                _progress(progress, 0.28, "Authoring a new Russian passage…")
                remaining = max(1, state.max_questions_per_skill - state.completed_count(state.active_skill))
                generated = GENERATOR.generate_and_store(
                    skill=state.active_skill,
                    level=_desired_generation_level(state),
                    mode=state.mode,
                    topics=state.topics,
                    competencies=state.competencies,
                    maximum_questions=min(remaining, 5 if state.active_skill == "reading" else 3),
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
                state.last_error = str(exc)
                LOGGER.warning(
                    "Fresh generation failed; using bank fallback session=%s skill=%s error_type=%s reason=%s",
                    state.session_id, state.active_skill, type(exc).__name__, str(exc)[:500],
                )
                safe_reason = html.escape(str(exc)[:500])
                state.last_content_note = (
                    f"Fresh generation did not produce an operational item ({type(exc).__name__}: {safe_reason}). "
                    "Your session was preserved and a validated bank item was loaded automatically."
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
<div class='timer-card strict' id='{element_id}' aria-live='assertive'>Remaining: --:--:--</div>
<script>
(() => {{ const el=document.getElementById('{element_id}'); const deadline={deadline_ms};
const draw=()=>{{const s=Math.max(0,Math.floor((deadline-Date.now())/1000));const h=String(Math.floor(s/3600)).padStart(2,'0');const m=String(Math.floor((s%3600)/60)).padStart(2,'0');const x=String(s%60).padStart(2,'0');if(el)el.textContent=`Remaining: ${{h}}:${{m}}:${{x}}`;}};draw();setInterval(draw,1000); }})();
</script>"""


def _status_text(state: SessionState, extra: str = "") -> str:
    completed = state.completed_count(state.active_skill)
    mode_name = {"training": "Training Mode", "diagnostic": "Adaptive Diagnostic", "simulation": "Full CA Simulation"}[state.mode]
    lines = [
        f"### {mode_name} — {state.active_skill.title()}",
        f"**Progress:** {completed}/{state.max_questions_per_skill} questions in this skill  |  **Session code:** `{state.session_id}`",
    ]
    if state.mode == "training":
        estimate = state.ability_for(state.active_skill)
        if estimate.practice_ilr:
            lines.append(f"Current provisional practice band: **ILR {estimate.practice_ilr}** ({estimate.confidence} confidence).")
    elif state.shortened_simulation:
        lines.append("**Shortened simulation:** this is not equivalent to a complete test.")
    else:
        lines.append("Adaptive calculations are hidden during strict testing conditions.")
    if state.content_source == "fresh_ai_preferred":
        health = BANK.health_summary()
        lines.append(
            f"**Content:** Fresh AI preferred · generated this session: {len(state.generated_passage_ids)} · "
            f"bank fallbacks: {state.bank_fallback_count} · reusable generated bank: "
            f"{health['generated_passages']} passages / {health['generated_questions']} questions."
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
        return f"### Russian Passage\n\n{passage.passage_ru}"
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
            outputs.append(gr.update(choices=[], value=None, visible=False, interactive=False))
    return outputs


def _blank_questions():
    outputs = []
    for _ in range(MAX_SLOTS):
        outputs.append(gr.update(value="", visible=False))
        outputs.append(gr.update(choices=[], value=None, visible=False, interactive=False))
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
    max_q = SIMULATION_LENGTHS[label]
    shortened = max_q < 35
    full = label.startswith("Full-length") or max_q >= 35
    seconds = 1800 if shortened else (10800 if label.startswith("Full-length") else 5400)
    return max_q, max_q, full, shortened, seconds


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
    progress=gr.Progress(),
):
    try:
        _progress(progress, 0.04, "Validating session settings…")
        mode = MODE_LABELS[mode_label]
        skills = SKILL_LABELS[skill_label]
        topics = _normalize_multiselect(topics, TOPICS, "topic")
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
        _progress(progress, 0.10, "Authorizing playback and preserving strict-mode state…")
        mark_listening_play(state)
        asset = BANK.get_audio(bundle.passage.audio_asset_id)
        if not asset:
            raise AudioError("No validated audio asset is linked to this passage.")
        _progress(progress, 0.30, "Loading validated audio…")
        path = resolve_audio_path(asset, ROOT)
        audio_note = ""
        if state.mode == "training" and (state.voice_label != "Starter-bank eSpeak voice" or state.speech_rate_label != "Normal"):
            voice_map = {"Russian Female — Svetlana": "ru-RU-SvetlanaNeural", "Russian Male — Dmitry": "ru-RU-DmitryNeural"}
            rate_map = {"Very slow": "-25%", "Slow": "-15%", "Normal": "+0%", "Fast": "+10%"}
            try:
                _progress(progress, 0.48, "Preparing the selected training voice and speed…")
                cache_dir = SETTINGS.audio_cache_runtime_path(ROOT)
                path = generate_cached_tts(bundle.passage.passage_ru, cache_dir, voice_map.get(state.voice_label, SETTINGS.edge_tts_voice), rate_map.get(state.speech_rate_label, "+0%"), timeout_seconds=SETTINGS.tts_timeout_seconds)
                audio_note = " Requested training voice/speed loaded from the deterministic TTS cache."
            except Exception as tts_exc:
                audio_note = f" Requested training voice/speed was unavailable; cached starter audio was used ({type(tts_exc).__name__})."
        _progress(progress, 0.82, "Preparing browser playback…")
        strict = state.mode in {"diagnostic", "simulation"}
        audio_html = controlled_audio_html(str(path), f"audio_{state.session_id}_{bundle.passage.id}_{state.current_listening_plays}", strict)
        STORAGE.save_checkpoint(state)
        _progress(progress, 1.0, "Audio ready")
        status = _status_text(state, f"Listening playback count for this passage: {state.current_listening_plays}.{audio_note}")
        return (
            state,
            gr.update(value=audio_html, visible=True),
            gr.update(interactive=not strict, visible=True),
            gr.update(value=status),
        )
    except Exception as exc:
        state.last_error = str(exc)
        STORAGE.save_checkpoint(state)
        return state, gr.update(value="", visible=False), gr.update(interactive=False), gr.update(value=_status_text(state, f"Recoverable audio error: {html.escape(str(exc))}"))


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
    lines = ["### Passage Feedback"]
    for index, record in enumerate(records, start=1):
        mark = "✅ Correct" if record.is_correct else "❌ Incorrect"
        lines.append(f"**{index}. {mark} — {record.stem_en}**")
        lines.append(f"- Correct answer: {record.correct_key}. {record.choices_snapshot[record.correct_key]}")
        lines.append(f"- Explanation: {record.rationale_en}")
        lines.append(f"- Russian evidence: `{record.evidence_ru}`")
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
            rendered[radio_output_index] = gr.update(value=answers_values[index], visible=True, interactive=True)
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
