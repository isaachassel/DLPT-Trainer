# Preset diagnostics and private audio authoring

## Current content status

All 51 original starter passages remain **draft/pending review** in `data/assessment/bank.json`, as requested. Their older `validation_status: accepted` is a deterministic practice-bank flag, not curator approval. Existing Training continues to use its original banks. No starter passage has been silently promoted.

The twelve original Russian 0+ listening scripts remain in `data/pilots/russian_0plus_dialogues.json` as authoring templates. The approved versions are now in `data/assessment/bank.json`, with twelve fixed ElevenLabs MP3s in `data/assessment/audio` and 24 English questions. The owner listened to and approved the audio, then authorized full approval for local noncommercial assessment workflow testing. Transcript/question consistency has been checked; the ILR labels remain provisional and uncalibrated.

For a local smoke test choose **Adaptive Assessment → Listening**, leave the eligible range at **0–3** (or set both bounds to **0+**), and use **2 minimum / 2 maximum passages**. For all twelve clips use **6 minimum / 12 maximum**. Answers and transcripts appear only in the final report. With the default maximum of 18, the run ends explicitly after twelve passages because the bank is exhausted. No passage repeats. Reading remains unavailable until approved reading content is added.

This narrow bank exercises selection, playback, submission, uncertainty, stopping, review and exports. It cannot test difficulty adaptation across levels. Reports explicitly identify the single tested band and warn that other model-estimated levels are extrapolations. A useful full-range adaptive bank still needs reading and listening passages spanning ILR 0–3.

## Local preview

Use the existing Python 3.12 virtual environment and pinned dependencies:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:GENERATION_PROVIDER='disabled'
$env:AUTO_PROVISION_DATASET_BANK='false'
$env:SYNC_GENERATED_BANK_ON_STARTUP='false'
$env:SYNC_GENERATED_BANK_ON_WRITE='false'
$env:GRADIO_ANALYTICS_ENABLED='False'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:GRADIO_SERVER_NAME='127.0.0.1'
.venv/Scripts/python.exe app.py
```

Open http://127.0.0.1:7860. No generation key is needed for preset assessments or the manual script editor. The workshop uses the existing `httpx` dependency; no ElevenLabs SDK or system installation is needed.

## Preset assessment boundary

`PresetBank` reads a deployment snapshot independently of the writable practice overlay. Adaptive Assessment, Adaptive Diagnostic and Simulation all use this snapshot, force bank-only selection and end-only feedback, and play fixed local audio. They do not call text generation, TTS, remote-bank prefetch or remote asset recovery. Old checkpoints referencing unapproved content are rejected safely.

The preset loader requires explicit approval with reviewer, date and reuse attestation, valid question relationships, supported levels, content hashes and verified local audio SHA-256. Invalid manifests fail closed; invalid/missing recordings are excluded with curator validation messages. Audio is rechecked before selection and playback. The shared app has no curator callback. A private JSON import can only create drafts in that user's workspace.

Answers, explanations and listening transcripts are retained in server-side Gradio State during assessment. Rendered controls contain only the passage orientation, English questions and choices, and reading text when applicable. Review is shown after the complete assessment ends. This is a practice application: included source-bank files in a public repository remain inspectable independently of the test UI.

The existing [adaptive method](ADAPTIVE_ASSESSMENT.md) is unchanged: a discrete Bayesian ability posterior with a multiple-choice guessing floor and a shared passage effect accounts for related questions. Reading/listening posteriors are separate. ILR labels supply provisional difficulty anchors, not calibrated item parameters. Minimum/maximum passage lengths, posterior uncertainty and content availability govern stopping. Results are **estimated practice ILR levels**, never official or validated ODA/DLPT scores.

## Private workshop

1. Open **Optional listening content workshop** and load the twelve drafts. Select and edit a script and its English questions. Save edits before preflight. Complete-package JSON import is also supported; all incoming review decisions are reset to draft and unfamiliar local file references are removed.
2. Enter **your own** ElevenLabs key. Credential checking reads subscription usage, models and Russian-language voices, with no audio generation. The visible password field is cleared after checking. The server retains the key only for this session. The web workshop never reads `ELEVENLABS_API_KEY` from the host environment.
3. Choose an available dialogue model and distinct voices for A and B (or edit the speaker-to-voice JSON for custom speaker IDs). The initial model is `eleven_v3`; model/voice availability depends on the account. This workflow has no voice-cloning endpoint. Voice suitability still needs audition and review.
4. Set an explicit **total input-character budget**, initially zero. It includes auditions, previous attempts and regenerations. Preflight displays every exact script, model, voice mapping, this-run characters and total reservations. The provider catalog also exposes documented model-rate metadata when available. Character counts are not a dollar or credit cap: account plans, model and voice rates can differ. Configure an account-side spending limit for a financial cap.
5. Optionally preflight and authorize a short **voice audition**. Then generate **First pilot only**. Play it and explicitly approve its voices before authorizing the remaining eleven. This voice decision does not approve content for the bank.
6. Use **Resume unfinished batch** after an interruption. Successful matching items are skipped. Each item has at most three paid attempts. Selected regeneration needs a new preflight and explicit spending confirmation.
7. Export the private ZIP before leaving. It contains draft `package.json`, accounting `ledger.json` and successful audio files. Audio previews and ZIP downloads use session-specific data payloads rather than shared filesystem URLs. No key is included. The JSON editor imports scripts/questions; durable reopening of an exported workspace (including its recordings/ledger) is available through the local CLI after extracting into a private folder.

The ledger is atomically saved **before** each paid request. Network failures, server errors, malformed audio and interrupted in-flight requests are treated as uncertain. They are not retried automatically. Check ElevenLabs request history, then explicitly acknowledge possible duplicate charges if retrying. Failed and uncertain character reservations stay counted conservatively. Completed clips survive later failures. There is no claim of provider-side idempotency or exactly-once charging.

Keys are kept in server memory and excluded from logs, metadata and exports. Private temporary directories are not in Gradio's allowed paths. Session cleanup deletes them (one-hour state TTL); startup also removes abandoned workspaces older than 24 hours. Export promptly: these are temporary workspaces, not durable cloud storage. Run shared deployments over HTTPS and on a host trusted with users' API credentials. Local administrators can access process memory and files.

Optional text drafting reuses `HostedProvider` with a separately supplied **Groq key**, one bounded request, and an explicitly constructed configuration with no inherited deployment credentials. Manual scripts require no text account. Legacy Training retains its existing provider/voice behavior and deployment credential requirements.

## Local environment workflow

Copy the placeholder `.env.example` to ignored `.env` locally and set `ELEVENLABS_API_KEY` there. Do not paste keys into scripts, package JSON, chat, source control or command-line arguments. Environment credentials are used only by this explicit local CLI, never by shared web sessions.

```powershell
.venv/Scripts/python.exe scripts/workshop.py init
# Edit storage/workshop/local/package.json if needed.
# Create an ignored storage/workshop/voices.json containing A/B voice IDs.
.venv/Scripts/python.exe scripts/workshop.py preflight --voices storage/workshop/voices.json --characters 8000
# Review the displayed plan before explicitly authorizing the first paid pilot:
.venv/Scripts/python.exe scripts/workshop.py generate --voices storage/workshop/voices.json --characters 8000 --confirm-spend
# Listen to the MP3 under storage/workshop/local/audio, then:
.venv/Scripts/python.exe scripts/workshop.py approve-voices
.venv/Scripts/python.exe scripts/workshop.py preflight --voices storage/workshop/voices.json --characters 8000 --kind batch
.venv/Scripts/python.exe scripts/workshop.py generate --voices storage/workshop/voices.json --characters 8000 --kind batch --confirm-spend
.venv/Scripts/python.exe scripts/workshop.py export
```

8000 is an illustrative character ceiling, not a quote or a required value. Explicitly choose your limit. A CLI workspace is deliberately durable and not subject to web-session deletion. `--workspace` resumes its saved ledger; reopening marks interrupted requests uncertain. To retry one, check provider history and use `--acknowledge-uncertain`. Use `--kind selected --item ru_pilot_01` for bounded regeneration. The CLI prints scripts/voice IDs, never the key.

## Curator approval and packaging

Only a trusted local operator with repository write access should run this command. Extract a user's ZIP into a private directory, inspect its files and review the transcript, questions, correct answers, distractors, intended level and actual audio. Listen for pronunciation, naturalness and voice suitability. Independently verify source, voice, model and plan rights before approving.

```powershell
.venv/Scripts/python.exe scripts/curate_assessment.py validate --package storage/workshop/local/package.json
.venv/Scripts/python.exe scripts/curate_assessment.py approve --package storage/workshop/local/package.json --item ru_pilot_01 --reviewer "Reviewer name" --notes "Record language/audio/ILR review and applicable reuse terms here" --attest-reuse-rights
```

Without `--package`, the curator reviews existing starter entries in the preset manifest. `reject` records a named rejection. An update to an approved item requires a higher content version and a fresh decision. Approval copies listening audio into `data/assessment/audio`, records its checksum and updates the manifest. Restart the app to load the reviewed snapshot. Review the resulting Git diff; **push/deploy remain separate authorized actions**. MP3s in that directory use Git LFS. Deployment must include real LFS assets, not pointer text. Never package a temporary provider URL.

## Official ElevenLabs references checked 2026-10-03

- [Text to Dialogue API](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert): `POST /v1/text-to-dialogue`, per-turn text/voice IDs, configurable model, Russian language code, MP3 output. This implementation limits each item to 2000 text characters and ten distinct speakers, uses no automatic HTTP retries, and does not request enterprise-only zero-retention options.
- [Russian voice discovery](https://elevenlabs.io/docs/api-reference/voices/search), [models](https://elevenlabs.io/docs/api-reference/models/list), [subscription usage](https://elevenlabs.io/docs/api-reference/user/subscription/get): account-scoped availability and usage metadata. Voice preview URLs are not downloaded by this app.
- [Dialogue capability and regeneration](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue): API regeneration may consume credits; dashboard regeneration benefits must not be assumed for API requests.
- [Publishing generated content](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform): free-plan output has noncommercial/attribution restrictions; paid-plan commercial rights depend on the applicable terms and creation-time subscription. Beta-service restrictions can prohibit production/commercial use. Upgrading later does not automatically change rights for earlier free output.
- [Terms of Use](https://elevenlabs.io/terms-of-use): users must hold necessary input/voice rights and follow applicable service terms. Public availability of a third-party recording is not a reuse license. Record creation-time tier and the curator's dated rights review; check current model status and the user's applicable contract before public redistribution.

Local live verification completed with twelve Russian Eleven v3 dialogues using Jessica and Eric. Account usage was 1,624 input characters against the owner's 2,000-character ceiling. The owner approved all twelve recordings and subsequently authorized their promotion for local assessment testing. The approved MP3s are now packaged with the assessment bank using Git LFS; credentials and the private workshop remain excluded from source control. Nothing has been publicly published by this step. See `data/assessment/audio/NOTICE.md` for the audio attribution and Free-plan limitations.

## Standing audio authorization

An owner may explicitly waive individual listening review for a demonstrated generation method. The trusted local workflow records this using `Workshop.authorize_audio_method(authorized_by, notes)` after pilot voice approval. The private workspace ledger stores the authorizer, instruction, date, provider, language, model and voice configuration. Future successful recordings matching that method receive an audio-only approval tied to the actual audio checksum, with `basis: standing_authorization`. This is not a claim that a person listened to each generated file.

Authorization persists on resuming that workspace, but is not inherited by other users or private sessions. A changed provider, model or voice configuration does not receive automatic approval. Character ceilings, attempt limits, error handling and separate question, ILR and reuse review remain in force. No audio authorization directly changes the production assessment manifest. The current owner's authorization covers the demonstrated ElevenLabs method; it does not increase the existing 2,000-character spending ceiling.

## Tests

Run `.venv/Scripts/python.exe -m pytest -q`. Mock tests cover account errors, rate/quota failures, uncertain responses, interrupted-batch recovery, reservation/attempt limits, pilot gating, session isolation, secret-free exports, path safety, curator-only writes, approved-only selection and provider-free assessment playback. Existing strong/weak/mixed/borderline and stopping tests continue to exercise the adaptive estimator. Fixture audio is clearly marked test data and never added to the production bank.

For repeatable browser QA only, run `.venv/Scripts/python.exe scripts/preview_fixtures.py` on loopback port 7861. It prominently labels its test-only review decisions and mock provider. Its unrelated fixture audio does not speak the draft scripts and must never be curated or distributed as ElevenLabs output. The main app on port 7860 has no mock-provider switch. Browser checks exercised a complete two-passage assessment, credential-free draft editing, missing-key blocking, mock pilot generation, pilot approval gating, eleven-item batch completion, private audio decoding and export-link creation.
