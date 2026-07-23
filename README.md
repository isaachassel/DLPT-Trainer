---
title: Russian Adaptive Proficiency Practice
emoji: 🎧
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: "6.5.1"
python_version: "3.11"
app_file: app.py
pinned: false
license: mit
---

# Russian Adaptive Proficiency Practice

An independent Russian Reading and Listening practice platform with Training, Adaptive Diagnostic, and strict computer-adaptive Simulation modes.

> **Important:** This is not official DLPT material. It is not affiliated with DLIFLC, DoD, or any government testing authority. It does not generate an official score. Every estimate is for practice guidance only.

## What happened to the original GenAI code

The original Hugging Face/Groq capability was **not removed**. The current release supports both providers, ordered fallback, user-requested fresh content, validation, TTS, and generated-bank storage.

Real API secret values are never stored in the repository. Use the same secret names in a local `.env` or Hugging Face Space secrets:

```text
HF_TOKEN
GROQ_API_KEY
```

The original environment names `GENAI_PROVIDER`, `HF_PROVIDER`, `HF_TEXT_MODEL`, and `GROQ_MODEL` remain supported. `GENERATION_PROVIDER` is the preferred replacement for `GENAI_PROVIDER` and takes precedence when both exist.

The original prompt file was not preserved line-for-line. Valuable level-specific Reading/Listening rules were rebuilt in `core/prompts.py`; unsafe fixed answer-letter sequences, fragile JSON extraction, overreliance on paragraph/word counts, and author self-verification were intentionally removed. See `docs/GENAI_AUDIT.md` for the exact audit and migration.

## Hybrid content architecture

The learner chooses one of two content policies:

1. **Validated bank only — fastest:** selects from the bundled starter bank and every previously accepted generated item.
2. **Fresh AI preferred:** attempts to author a new passage bundle near the active skill estimate. The new bundle must pass typed schema validation, deterministic gates, independent passage audit, blind answer verification, Python answer shuffling, duplicate checks, and Listening audio validation before it is shown. Accepted content is stored and becomes reusable. Any provider, quota, schema, validation, duplicate, timeout, persistence, or TTS failure falls back to an accepted bank item without clearing progress.

The bank is the application’s reliability layer and accumulated content memory—not a replacement for live generation.

## Main capabilities

- Independent Bayesian Reading and Listening estimates.
- Posterior uncertainty and evidence-aware practice reports.
- Information-based selection with topic, genre, question-type, and exposure balancing.
- Meaningful Training target-level bias.
- Variable bundles: Reading 1–5 questions and Listening 1–3 questions.
- Strict Simulation timing, locked navigation, and controlled one-play Listening.
- Session checkpoints, recovery, optional history, and JSON/CSV export.
- Typed Pydantic bank, session, generation, validation, and reporting models.
- Provider-independent starter content.
- Optional staged live generation with repair, quarantine, persistence, quota protection, and bank fallback.
- Python-side answer shuffling and key remapping; prompts never prescribe answer letters.

## Modes

### Training Mode

- Reading, Listening, or separate Reading + Listening sections.
- Starting and target ILR bands.
- Topic and comprehension-competency emphasis.
- Optional hints and passage-level review.
- Listening replay, optional voice/speed variants, and post-answer transcript review.
- Bank-only or Fresh-AI-preferred content.

### Adaptive Diagnostic

- Independent Reading and Listening posteriors.
- Broad medium prior.
- End-only feedback.
- No learner-selected slow audio or voice changes.
- Minimum evidence plus confidence-aware stopping.
- Provider/loading time is excluded from the assessment timer.

### Full CA Simulation

- Reading and Listening run as separate sections.
- Medium-difficulty opening passage.
- No skipping, back navigation, or answer changes after passage submission.
- All questions in the bundle must be answered before advancing.
- Strict countdown timer.
- Shortened simulations are clearly labeled.
- A full simulation never completes below 35 questions per selected skill.
- One controlled Listening play, no replay, and no transcript during the active simulation.

## Starter and generated item banks

The repository ships with:

- 27 starter passages;
- 88 starter questions;
- 48 Reading questions and 40 Listening questions;
- 15 bundled Listening audio assets;
- balanced starter keys: A=22, B=22, C=22, D=22 before session shuffling.

Immutable starter bank:

```text
data/starter_items.jsonl
```

Writable generated overlay:

```text
storage/item_bank/generated_items.jsonl
```

With `PERSISTENT_STORAGE_PATH=/data`:

```text
/data/item_bank/generated_items.jsonl
```

The two files are indexed as one operational bank. Failed candidates are written under `storage/quarantine/` or `/data/quarantine/` and never become selectable.

All starter and generated difficulty values remain **provisional** until empirical calibration exists.

## GenAI authoring pipeline

A fresh bundle uses separate controlled stages:

1. Russian passage/transcript authoring.
2. Deterministic passage checks.
3. Independent passage naturalness/level audit.
4. Bounded passage repair when needed.
5. Separate English question/choice authoring.
6. Deterministic question and distractor checks.
7. Blind verification with choices reordered and the proposed answer hidden.
8. Optional second verifier for higher-risk ILR 2+/3 items.
9. Bounded question-set repair when needed.
10. Python choice shuffling, correct-key remapping, and bank-position balancing.
11. Listening TTS creation and validation.
12. Atomic generated-bank persistence or redacted quarantine.

Provider responses prefer strict JSON Schema, then best-effort schema, then JSON-object fallback. Every result must still pass strict Pydantic validation.

Generated metadata records author/verifier providers and models, prompt/pipeline version, request count, repair count, and token totals when the provider reports them.

## Local setup

Python 3.10 or 3.11 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:7860`.

Validation and tests:

```bash
pip install -r requirements-dev.txt
python scripts/check_space_dependencies.py
python scripts/validate_item_bank.py
pytest -q
python scripts/smoke_test_space.py
```

## Dependency compatibility

The Space metadata pins Gradio `6.5.1`. Hugging Face installs that release with its `oauth` and `mcp` extras, so the production dependency set pins Pydantic `2.12.5`, the newest version accepted by the Gradio 6.5.1 MCP extra. Do not raise the Pydantic pin independently without also checking the selected Gradio release.

Production dependencies live in `requirements.txt`. Test-only packages such as `pytest` live in `requirements-dev.txt` so they are not installed in the public Space container. The repository includes `python scripts/check_space_dependencies.py`, which checks the pinned versions against the installed Gradio dependency metadata before release.

## Enabling live generation locally

Add at least one key to `.env`:

```text
ENABLE_USER_GENERATION=true
GENERATION_PROVIDER=hf_then_groq
VERIFICATION_PROVIDER=auto
HF_TOKEN=your_hugging_face_token
GROQ_API_KEY=your_groq_key
```

One matching key is sufficient. When both are present, `VERIFICATION_PROVIDER=auto` prefers the reverse provider order for auditing and blind verification.

Current defaults:

```text
HF_PROVIDER=auto
HF_TEXT_MODEL=openai/gpt-oss-120b
HF_VERIFIER_MODEL=openai/gpt-oss-20b
GROQ_MODEL=openai/gpt-oss-120b
GROQ_VERIFIER_MODEL=openai/gpt-oss-20b
STRUCTURED_OUTPUT_MODE=auto
```

Original configuration remains compatible:

```text
GENAI_PROVIDER=hf_then_groq
HF_PROVIDER=auto
HF_TEXT_MODEL=your_supported_model
GROQ_MODEL=your_supported_model
```

Do not set both `GENERATION_PROVIDER` and `GENAI_PROVIDER` to conflicting values.

### Cost, retry, and quality controls

```text
MAX_GENERATION_REQUESTS_PER_SESSION=8
GENERATION_CONCURRENCY_LIMIT=1
PROVIDER_TIMEOUT_SECONDS=45
PROVIDER_MAX_RETRIES=2
MAX_PROVIDER_ATTEMPTS_PER_STAGE=4
GENERATION_AUDIT_MODE=always
GENERATION_REPAIR_ATTEMPTS=1
SECOND_VERIFIER_HIGH_RISK=true
AUTHORING_TEMPERATURE=0.25
VERIFICATION_TEMPERATURE=0.0
PASSAGE_MAX_TOKENS=3200
QUESTION_MAX_TOKENS=2600
REPAIR_MAX_TOKENS=3200
AUDIT_MAX_TOKENS=1200
VERIFIER_MAX_TOKENS=900
```

Configured token values are hard caps. The application applies smaller stage-, level-, and bundle-aware budgets when appropriate.

`GENERATION_AUDIT_MODE=smart` saves one audit call only for lower-risk Reading Training content. Diagnostic, Simulation, Listening, ILR 2+, and ILR 3 continue to receive the passage audit. `off` is supported but produces a startup warning.

## Hugging Face Spaces deployment

1. Create a **Gradio** Space.
2. Upload all repository contents to the Space root.
3. The starter bank launches without secrets.
4. Add provider secrets in **Settings → Variables and secrets** to enable Fresh AI.
5. Attach persistent storage and set `PERSISTENT_STORAGE_PATH=/data` to retain generated items across rebuilds.
6. Run a short Training session and the smoke test after deployment.

### Required Space secrets

None for bank-only operation.

### Fresh-AI secrets

At least one:

```text
HF_TOKEN
GROQ_API_KEY
```

### Recommended Space variables

```text
ENABLE_USER_GENERATION=true
GENERATION_PROVIDER=hf_then_groq
VERIFICATION_PROVIDER=auto
STRUCTURED_OUTPUT_MODE=auto
GENERATION_AUDIT_MODE=always
GENERATION_REPAIR_ATTEMPTS=1
SECOND_VERIFIER_HIGH_RISK=true
MAX_GENERATION_REQUESTS_PER_SESSION=8
GENERATION_CONCURRENCY_LIMIT=1
PROVIDER_TIMEOUT_SECONDS=45
PROVIDER_MAX_RETRIES=2
MAX_PROVIDER_ATTEMPTS_PER_STAGE=4
QUEUE_CONCURRENCY_LIMIT=4
ENABLE_HISTORY=true
ENABLE_ANALYTICS=false
CHECKPOINT_AFTER_PASSAGE=true
PERSISTENT_STORAGE_PATH=/data
```

Never commit real keys. Settings excludes secret fields from model serialization, provider errors are redacted, and quarantine persistence recursively removes secret-bearing strings.

## Administrator authoring

The same staged validation pipeline is available offline:

```bash
python scripts/generate_items.py --skill reading --level 2 --count 2
python scripts/generate_items.py --skill listening --level 2+ --count 2 --topic economics
```

Then validate the combined bank:

```bash
python scripts/validate_item_bank.py
```

## Persistence and restart behavior

Default Space disk is ephemeral. Without mounted storage, generated items remain reusable during the current runtime but may disappear after a rebuild or restart. With `PERSISTENT_STORAGE_PATH=/data`, generated items, checkpoints, history, quarantine records, exports, and audio cache use the mounted volume.

The application checkpoints after each submitted passage. Provider failure does not delete completed responses, and generation/loading time is added back to active timer anchors.

## Troubleshooting

### Build fails with `ResolutionImpossible` for Pydantic

Confirm the repository contains exactly:

```text
gradio==6.5.1
pydantic==2.12.5
```

Hugging Face adds `gradio[mcp,oauth]==6.5.1` during the build. Its MCP extra rejects Pydantic versions above `2.12.5`. A stale `pydantic==2.13.4` line will reproduce the dependency-resolution failure before the application starts. Commit the corrected `requirements.txt`, then use **Factory reboot** or trigger a new commit so the Space rebuilds from the new dependency file.


### Fresh AI always falls back

Confirm:

- `ENABLE_USER_GENERATION=true`;
- a supported `GENERATION_PROVIDER` is selected;
- a matching secret exists;
- the configured model is available to the selected provider;
- quota/rate limits are available;
- `MAX_GENERATION_REQUESTS_PER_SESSION` is above zero;
- the candidate is not being rejected by validation or duplicate checks.

The setup banner reports readiness and configuration warnings. Quarantine records include stage traces and redacted failure reasons.

### Generated items disappear after restart

Attach persistent storage and set:

```text
PERSISTENT_STORAGE_PATH=/data
```

### A candidate fails validation

This is expected fail-closed behavior. Inspect:

```text
storage/quarantine/live_generation_failures.jsonl
```

The failed item remains outside the operational bank.

### Listening audio does not play or logs show `/graphql` 405 / `Invalid file descriptor: -1`

Version 1.2.3 explicitly launches Gradio with `ssr_mode=False`. The application does not need Gradio's experimental Node SSR layer, which can emit `/graphql` 405 responses and event-loop finalizer warnings on Hugging Face Spaces.

Listening MP3 files are served through Gradio's byte-range-capable file route instead of being base64-embedded in callback output. Only `data/audio/` and the controlled runtime TTS cache are exposed through `allowed_paths`. If browser autoplay is blocked, press **Play / Replay Audio** again.

Starter audio is bundled. Fresh Listening content requires successful TTS creation and validation before acceptance. If TTS fails, the session falls back to bank content without clearing completed responses.

### Session interrupted

Use the displayed recovery code under **Recover a Checkpoint**. A corrupted checkpoint is rejected safely.

## Repository structure

```text
app.py
core/
  adaptive.py
  audio.py
  config.py
  constants.py
  generation.py
  item_bank.py
  models.py
  prompts.py
  reporting.py
  scoring.py
  session.py
  storage.py
  validation.py
ui/
  callbacks.py
  layout.py
data/
  starter_items.jsonl
  audio/
  schemas/
scripts/
  generate_items.py
  validate_item_bank.py
  calibrate_items.py
  smoke_test_space.py
tests/
docs/
  ORIGINAL_AUDIT.md
  GENAI_AUDIT.md
  ARCHITECTURE.md
  TEST_RESULTS.md
  KNOWN_LIMITATIONS.md
requirements.txt
.env.example
LICENSE
```

See `docs/GENAI_AUDIT.md`, `docs/TEST_RESULTS.md`, and `docs/KNOWN_LIMITATIONS.md` for details.
