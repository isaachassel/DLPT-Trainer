"""Optional private workshop. No shared-bank write or approval endpoint exists here."""
import base64
import html
import json

import gradio as gr

from core.content_workshop import Workshop, cleanup_old_workspaces
from core.dialogue_authoring import DialogueDraft, author, materialize
from core.preset_bank import ContentPackage


def _session(value):
    return value if value is not None else Workshop()


def _editor(work, selected=None):
    item = next((x for x in work.package.items if x.id == selected), work.package.items[0] if work.package.items else None)
    if not item:
        return "{}"
    return DialogueDraft(topic=item.passage.topic, orientation_en=item.passage.orientation_en,
                         speakers=item.speakers, turns=item.turns,
                         questions=[{k: getattr(q, k) for k in ("stem_en", "choices", "correct_key", "rationale_en", "evidence_ru")}
                                    for q in item.questions]).model_dump_json(indent=2)


def build_workshop():
    cleanup_old_workspaces()
    with gr.Accordion("Optional listening content workshop — use your own ElevenLabs credits", open=False):
        gr.Markdown(
            "An ElevenLabs account and API access are required **only for generating audio**. "
            "Each paid run uses the key you enter in this private session. The app never fills it from the owner's environment. "
            "Manual scripts need no text-model key. Optional AI drafting uses your separate Groq account. "
            "Scripts sent for generation are subject to the provider's retention terms. No voice cloning is offered.\n\n"
            "**All outputs stay drafts.** Export before leaving: private server workspaces expire after inactivity and are deleted "
            "on session cleanup. Shared-bank approval is a separate local curator command. Legacy Training's Fresh AI option "
            "uses the deployment's configured text provider; its voice playback uses the existing Edge/Piper setup.")
        state = gr.State(None, time_to_live=3600, delete_callback=lambda w: w.close() if w else None)
        status = gr.Markdown("Load the twelve pending-review scripts to begin. No audio has been generated for these drafts.")
        load = gr.Button("Load / resume private draft workspace")
        selected = gr.Dropdown(label="Draft item", choices=[])
        editor = gr.Code(label="Edit selected script and English questions (JSON)", language="json", lines=14)
        save = gr.Button("Save selected draft edits")
        package = gr.Code(label="Import / edit complete package JSON (optional)", language="json", lines=5)
        import_btn = gr.Button("Import package JSON as private drafts")
        with gr.Accordion("Optional AI script authoring — separate Groq credentials", open=False):
            text_key = gr.Textbox(label="Your Groq API key (cleared after use)", type="password")
            text_model = gr.Textbox(label="Groq model", value="openai/gpt-oss-120b")
            topic = gr.Textbox(label="Everyday situation for a Russian 0+ draft")
            text_consent = gr.Checkbox(label="Send this topic to my Groq account for one text-generation request")
            text_btn = gr.Button("Create and append draft")
        key = gr.Textbox(label="Your ElevenLabs API key (server session only; cleared after checking)", type="password")
        check = gr.Button("Check credentials and list available voices / models (no audio generation)")
        catalog = gr.JSON(label="Account usage and available voices / models")
        gr.Markdown("Import Russian or Mandarin listening scripts in one language per workspace. Multilingual voices can be auditioned; pronunciation and accent still require review. The built-in templates and optional text drafting start in Russian.")
        model = gr.Dropdown(label="Dialogue model (choose one supported by Text to Dialogue)", choices=["eleven_v3"], value="eleven_v3")
        voice_a = gr.Dropdown(label="Voice for A (wife / first speaker)", choices=[])
        voice_b = gr.Dropdown(label="Voice for B (husband / second speaker)", choices=[])
        voices = gr.Code(label="Speaker → voice IDs (supports custom speakers; filled by A/B selection)", language="json", value='{"A": "", "B": ""}', lines=3)
        budget = gr.Number(label="Total input-character budget for this workspace (including auditions, failed requests and regenerations)", value=0, precision=0)
        action = gr.Radio(label="Next paid action", choices=[("Short voice audition", "audition"), ("First pilot only", "pilot"),
                                                                 ("Resume unfinished batch", "batch"), ("Generate / regenerate selected item", "selected")], value="pilot")
        uncertain = gr.Checkbox(label="For an uncertain earlier request: I checked provider history and accept possible duplicate charges")
        preflight = gr.Button("Prepare preflight — no audio spending")
        plan = gr.JSON(label="Review exact scripts, model, voices and usage before confirming")
        paid_consent = gr.Checkbox(label="I reviewed this preflight and authorize charging my ElevenLabs account within its character limit")
        generate = gr.Button("Generate the reviewed plan (consumes credits)")
        voice_consent = gr.Checkbox(label="I listened to the first pilot and approve these voices for the remaining batch")
        approve = gr.Button("Record pilot voice approval (content remains draft)")
        preview = gr.Button("Play selected successful clip")
        audition = gr.Button("Play successful voice audition")
        audio = gr.HTML()
        export = gr.Button("Export private draft package and successful audio")
        download = gr.HTML()
        clear = gr.Button("Discard private workspace and credentials")

        def load_cb(w):
            w = _session(w)
            return w, gr.update(choices=[x.id for x in w.package.items], value=w.package.items[0].id if w.package.items else None), _editor(w), w.package.model_dump_json(indent=2), "Private workspace loaded. All items are pending review."

        load.click(load_cb, [state], [state, selected, editor, package, status], api_visibility="private")
        selected.change(lambda w, i: _editor(w, i) if w else "{}", [state, selected], editor, api_visibility="private")

        def save_cb(w, i, raw):
            w = _session(w)
            try:
                draft = DialogueDraft.model_validate_json(raw)
                prior = next(x for x in w.package.items if x.id == i)
                item = materialize(draft, i, language=prior.passage.language, target_ilr=prior.passage.target_ilr)
                data = ContentPackage(items=[item if x.id == i else x for x in w.package.items])
                w.edit(data.model_dump_json())
                return w, w.package.model_dump_json(indent=2), "Saved edits; changed audio and pilot approval were invalidated."
            except Exception:
                return w, gr.update(), "Draft rejected. Check JSON, speakers, A–D options, correct keys and exact evidence."
        save.click(save_cb, [state, selected, editor], [state, package, status], api_visibility="private")

        def import_cb(w, raw):
            w = _session(w)
            try:
                w.edit(raw)
                return load_cb(w)
            except ValueError as exc:
                return w, gr.update(), gr.update(), gr.update(), str(exc)
        import_btn.click(import_cb, [state, package], [state, selected, editor, package, status], api_visibility="private")

        def text_cb(w, k, m, t, consent):
            w = _session(w)
            try:
                if not consent:
                    raise ValueError("Confirm the separate text request first, or edit a manual script")
                item = author(k, m, t)
                w.edit(ContentPackage(items=[*w.package.items, item]).model_dump_json())
                return (*load_cb(w), "", False)
            except ValueError as exc:
                return w, gr.update(), gr.update(), gr.update(), str(exc), "", False
        text_btn.click(text_cb, [state, text_key, text_model, topic, text_consent],
                       [state, selected, editor, package, status, text_key, text_consent], api_visibility="private")

        def check_cb(w, k):
            w = _session(w)
            try:
                c = w.configure(k)
                ms = [m["model_id"] for m in c["models"]]
                vs = [(v["name"] + " · " + v["voice_id"], v["voice_id"]) for v in c["voices"]]
                return w, "", c, gr.update(choices=ms, value="eleven_v3" if "eleven_v3" in ms else (ms[0] if ms else None)), gr.update(choices=vs), gr.update(choices=vs), "Credentials checked. Select distinct voices; no audio credits spent."
            except Exception:
                return w, "", None, gr.update(), gr.update(), gr.update(), "Credential check failed. Check key permissions for subscription, models and voices, account access, quota and connection. No audio request sent."
        check.click(check_cb, [state, key], [state, key, catalog, model, voice_a, voice_b, status], api_visibility="private")
        for control in [voice_a, voice_b]:
            control.change(lambda a, b: json.dumps({"A": a or "", "B": b or ""}), [voice_a, voice_b], voices, api_visibility="private")

        def preflight_cb(w, m, v, b, a, i, u):
            w = _session(w)
            try:
                p = w.preflight(m, json.loads(v), b, a, i, u)
                return w, p, False, "Preflight prepared. Confirm only after reviewing every script and setting."
            except (ValueError, TypeError) as exc:
                w.plan = None
                return w, None, False, html.escape(str(exc))
        preflight.click(preflight_cb, [state, model, voices, budget, action, selected, uncertain], [state, plan, paid_consent, status], api_visibility="private")

        def generate_cb(w, consent):
            try:
                if not consent or not w:
                    raise ValueError("Prepare and explicitly authorize the displayed preflight first")
                return w, w.generate(), False, w.package.model_dump_json(indent=2), None
            except ValueError as exc:
                return w, str(exc), False, gr.update(), None
        generate.click(generate_cb, [state, paid_consent], [state, status, paid_consent, package, plan], api_visibility="private", trigger_mode="once")

        def approve_cb(w, consent):
            try:
                if not w or not consent:
                    raise ValueError("Listen to the pilot and confirm your voice choice first")
                w.approve_voices()
                return w, "Pilot voices approved for this model/voice configuration. Content is still draft."
            except ValueError as exc:
                return w, str(exc)
        approve.click(approve_cb, [state, voice_consent], [state, status], api_visibility="private")

        def preview_cb(w, i):
            try:
                return w.preview(i) if w else "Load a private workspace first."
            except ValueError as exc:
                return html.escape(str(exc))
        preview.click(preview_cb, [state, selected], audio, api_visibility="private")
        audition.click(lambda w: preview_cb(w, "voice_audition"), [state], audio, api_visibility="private")

        def export_cb(w):
            if not w:
                return "Load a workspace first."
            try:
                data = base64.b64encode(w.export()).decode()
                return f'<a download="dlpt-drafts.zip" href="data:application/zip;base64,{data}">Download private draft package</a>'
            except ValueError as exc:
                return html.escape(str(exc))
        export.click(export_cb, [state], download, api_visibility="private")

        def clear_cb(w):
            if w:
                w.close()
            return None, "Workspace and credentials discarded.", "", "", "", "", None, None, gr.update(choices=[], value=None), "", "", False, False
        clear.click(clear_cb, [state], [state, status, editor, package, audio, download, catalog, plan, selected, key, text_key, paid_consent, voice_consent], api_visibility="private")
