---


title: "Russian & Mandarin Adaptive Proficiency Practice"
emoji: 🎧
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: "6.5.1"
python_version: "3.11"
app_file: app.py
pinned: false
---

# Russian & Mandarin Adaptive Proficiency Practice

## Adaptive Assessment

Select **Adaptive Assessment** for separate reading/listening practice estimates, a 90% uncertainty interval, configurable passage limits, and explicit stopping reasons. The mode accounts for guessing and shared-passage evidence, avoids repeats, and withholds review until the assessment ends. Results use provisional ILR labels and are not official or validated ODA/DLPT scores. See [setup, scoring assumptions, limitations, and verification](docs/ADAPTIVE_ASSESSMENT.md).

## v1.8.0 Submit Passage reliability

The **Submit Passage** action now runs as one direct queued Gradio event. This fixes a production case where the old `queue=False` prepare -> `.then(...)` chain could disable the button but never invoke Python, leaving the UI apparently frozen and the Space log completely silent. The new event emits a visible **Submitting…** state without touching answers or the active nonce, logs receipt before scoring, saves the checkpoint, performs adaptive selection, and renders the next passage from the same callback.

If submission ever fails outside the normal recovery path, the app restores the current passage and selected radio answers rather than leaving the button disabled.

## v1.7.9 verifier recovery

Fresh-AI passages are no longer discarded solely because a hosted blind verifier returns an incomplete or misnumbered batch. The app preserves valid verification entries, normalizes an unambiguous one-based batch, and independently re-verifies only missing or duplicate indexes with the single-question verifier contract. This specifically fixes the production Level 3 Reading fallback `Blind verifier did not return exactly one result for every question.` while keeping blind answer verification mandatory.

An independent Russian and Mandarin Chinese Reading/Listening practice platform with Training, Adaptive Diagnostic, and a strict DLPT-style adaptive practice simulation.

Choose **Russian** or **Mandarin Chinese** before starting. Half of the bundled ILR 2+/3 Mandarin Reading passages use Traditional characters, and high-level Fresh-AI Reading requests deliberately cover both Simplified and Traditional characters. Every language has separate Reading/Listening indexes, exposure history, adaptive selection, generated-bank filtering, and TTS voice routing. Changing languages never mixes source passages, questions, audio, or ability evidence.

> **Important:** This is not official DLPT material. It is not affiliated with DLIFLC, DoD, or any government testing authority. It does not generate an official score or DLPT prediction. Provisional working bands are for practice guidance only.

### Audio behavior in v1.7.8

The default **Automatic natural Russian voice** keeps Microsoft Edge TTS for the strongest free online voices: Dmitry and Svetlana. Single-speaker news, narration, announcements, and lectures remain one continuous recording. The app does not cut ordinary passages into sentence fragments.

The free Edge endpoint used by this Space does not currently accept `ru-RU-DariyaNeural`, even though that name appears in broader Microsoft voice documentation. The unavailable Dariya choice has therefore been removed instead of presenting a selector that silently plays another voice. Existing saved sessions that selected Dariya migrate to **Irina (local Piper)**.

## Hybrid multi-speaker listening audio

Version 1.7.8 retains the mixed role/name dialogue fix for scripts such as `Менеджер:` / `Алексей:`, validates multi-speaker formatting before audio creation, and remembers the working Gemini runtime model after Google rejects a retired alias.

Version 1.7.8 retains the two completely free engines introduced in v1.7.0:

- Microsoft Edge TTS: Dmitry and Svetlana
- Local Piper TTS: Irina and Ruslan

Detected dialogue is split only at reliable speaker turns. Labels are removed before synthesis, each speaker keeps one stable profile, and the completed turns are joined into one playable MP3. Russian scripts can therefore use four distinct voices before any voice must be reused:

```text
Speaker 1 → Dmitry (Edge)
Speaker 2 → Svetlana (Edge)
Speaker 3 → Irina (local Piper)
Speaker 4 → Ruslan (local Piper)
```

Piper models are downloaded only when one of those supplemental voices is actually needed. Each medium Russian model is about 63 MB and is cached after its first use, so the app does not add both models to every startup. Manual Training choices now clearly identify whether a voice uses Edge or local Piper.

Fresh AI multi-speaker scripts are limited to two through four speakers and must use stable explicit labels. Multi-speaker generated-bank assets produced before the v1.7.5 speaker-parser cache bump are regenerated once when selected, so an older one-narrator MP3 cannot bypass the repaired dialogue renderer. If a supplemental voice cannot load, automatic/canonical audio can fall back safely; an explicit Training selection reports the actual fallback rather than pretending the requested voice played.


## Performance behavior in v1.7.8

This release preserves the v1.7.1 performance design and v1.7.2 startup/provider resilience without changing assessment behavior. Startup restores the generated JSONL bank immediately but no longer downloads every saved MP3. A generated Listening file is fetched only when selected, and that one file begins prefetching in the background while the learner reads.

The same selected-item prefetch warms any required neural Training or strict-mode upgrade. Multi-speaker Edge turns are rendered with a bounded three-request pool, while Piper remains serialized to protect free CPU memory. Fresh-AI Listening uses an explicit learner-selected Training voice and speed for its first durable render, so playback does not synthesize the same passage a second time when the requested profile already matches.

For Automatic voice mode, the durable generated-bank recording remains at the stable natural speed, but v1.7.8 immediately starts the learner-selected Fast/Slow/Normal Training render in the background as soon as a fresh Listening item is accepted. This closes the gap where Fresh-AI items were not entering the same prefetch path as bank-selected items.

Operational passage validation and bank-health totals are cached in memory and invalidated only when the bank changes. Reading and bank-only selection therefore avoid repeating the same Pydantic/deterministic validation work on every Next Passage action.

## Stable topic taxonomy and anti-repetition

The topic selector now exposes only a stable set of broad DLPT-style categories. AI-authored subtopics such as `bike lanes`, `urban transportation / bike sharing`, `library hours`, or `utility outage` remain metadata beneath their broad category and are no longer appended as new top-level selector choices.

When the topic box is blank, the server favors underrepresented categories, strongly avoids the most recent Fresh-AI categories, and rejects repeated or near-repeated themes. Starter-bank file order is not treated as learner recency. Explicitly selected categories are still honored.

Provider quota handling is also bounded: a Hugging Face 402 or Groq 429 activates a shared cooldown across authoring and verification stages instead of repeatedly calling the same unavailable free endpoint. If every configured provider is cooling down, Fresh AI immediately uses an accepted bank item. Structured-output 400 responses are remembered per provider/model so later stages reuse a compatible JSON mode rather than repeating a rejected request.

## Runtime resilience in v1.7.8

Gradio and Hugging Face telemetry are disabled before the interface is built. This removes the short-lived telemetry event loops that produced misleading `Invalid file descriptor: -1` cleanup tracebacks even though the Space had already returned HTTP 200. Expected free-tier quota and rate-limit recoveries are logged concisely, while unexpected application errors still remain visible.

For hosted question generation, a valid verified subset may be retained when one question in a batch fails deterministic checks. This avoids an immediate repair call that can trigger Groq free-tier rate limits, while still requiring passage audit, local validation, and blind answer verification. Compatible v1.7.0 neural recordings are also reused when their voice and rate match, preventing needless Listening regeneration after an app upgrade.

The blind-verification batch now sends Groq a smaller transport schema while retaining the full Pydantic constraints locally. If Groq still rejects constrained decoding with HTTP 400, the verifier stays on Groq and retries in JSON Object Mode before falling back to Gemini, preserving independent verification whenever Groq itself is healthy.

## Free GenAI routing in v1.7.8

Fresh-AI authoring now defaults to **Gemini 3.1 Flash-Lite → Groq GPT-OSS** instead of spending Hugging Face Inference Providers credits first. Hugging Face remains the generated-bank storage layer, but hosted HF inference is disabled by default. This separation matters because a write-capable `HF_BANK_TOKEN` can keep the private Dataset bank durable without consuming the very small monthly HF inference allowance.

Recommended free setup:

```text
GEMINI_API_KEY=<free Google AI Studio key>
GROQ_API_KEY=<existing Groq key>
HF_BANK_TOKEN=<write-capable Hugging Face token for the private generated bank>
GENERATION_PROVIDER=gemini_then_groq
VERIFICATION_PROVIDER=auto
ENABLE_HF_INFERENCE=false
```

Before its first Gemini generation, the app calls Google's model-list endpoint with the configured key and filters to models that support `generateContent`. Version 1.7.8 defaults to the stable low-latency `gemini-3.1-flash-lite` route and shares the discovered catalog, rejected aliases, and last known-good model across author and verifier adapters. A retired alias is therefore tried at most once per running Space. Stable 2.x/3.1 routes use `responseMimeType` + `responseJsonSchema`, while newer routes can use `responseFormat`; provider-specific HTTP 400 handling remains bounded before another provider is used.

If model discovery returns HTTP 400/401/403, the log reports a Gemini key/project authentication problem instead of pretending the model is missing. A 200 model-list response proves the key is accepted and lets the app select an actually available model. You normally should not set `GEMINI_MODEL` manually; the default is only a preference and runtime discovery is authoritative.

With `VERIFICATION_PROVIDER=auto`, authoring prefers Gemini while passage audits and blind answer verification prefer Groq. This spreads the multi-stage workload across independent providers instead of spending Groq's per-minute GPT-OSS token budget on passage authoring, question authoring, and verification back-to-back. If one provider is rate-limited, the existing cooldown/circuit-breaker path uses the other provider or immediately falls back to the validated bank.

Existing Spaces that still contain `GENERATION_PROVIDER=hf_then_groq` do not have to be reconfigured immediately: when `GEMINI_API_KEY` is present and `PREFER_GEMINI_IF_AVAILABLE=true`, v1.7.8 automatically promotes Gemini ahead of that legacy chain while `ENABLE_HF_INFERENCE=false` keeps HF inference out of normal generation. Setting `GENERATION_PROVIDER=gemini_then_groq` is still recommended for clarity.

Cerebras REST support is included only as an optional alternate route for users who already have usable credits/access; it is **not** part of the default all-free configuration.

Google's Gemini free tier is free of charge but its pricing terms state that free-tier content may be used to improve Google products. Do not put private or sensitive learner information into generation prompts. This app's normal prompts contain assessment-generation instructions and target-language content rather than learner identity data.

Real API secret values are never stored in the repository. The original `GENAI_PROVIDER`, `HF_PROVIDER`, `HF_TEXT_MODEL`, and `GROQ_MODEL` environment names remain supported. `GENERATION_PROVIDER` is the preferred replacement for `GENAI_PROVIDER` and takes precedence when both exist.

The original prompt file was not preserved line-for-line. Valuable level-specific Reading/Listening rules were rebuilt in `core/prompts.py`; unsafe fixed answer-letter sequences, fragile JSON extraction, overreliance on paragraph/word counts, and author self-verification were intentionally removed. See `docs/GENAI_AUDIT.md` for the exact audit and migration.

## Hybrid content architecture

The learner chooses one of two content policies:

1. **Validated bank only — fastest:** selects from the bundled starter bank and every previously accepted generated item.
2. **Fresh AI preferred:** available in Training, Diagnostic, and Simulation. It attempts to author a new passage bundle near the active skill estimate. The new bundle must pass typed schema validation, deterministic gates, automated passage audit, blind answer verification, Python answer shuffling, duplicate checks, and Listening audio validation before it is shown. No human-vetting gate is required. Accepted content is stored and becomes reusable. Any provider, quota, schema, validation, duplicate, timeout, persistence, or TTS failure falls back to an accepted bank item without clearing progress.

### Bank terminology and write behavior

- **Built-in validated starter** is immutable content shipped with the app.
- **Saved AI-generated** contains only accepted Fresh-AI bundles and explicit imports.
- **Ready to use now** is the validated selectable total from both sources; it is not a third bank.
- A **Validated bank only** session never writes a content record. Selecting, answering, replaying, or checkpointing an existing item leaves `generated_items.jsonl` unchanged.

See `docs/BANK_COUNTS_AND_WRITE_RULES.md`.

The bank is the application’s reliability layer and accumulated content memory—not a replacement for live generation.

## Main capabilities

- Russian and Mandarin practice from one language selector, including Simplified/Traditional coverage in high-level starter and generated Reading.
- Bundled Mandarin starter bank: 12 Reading passages / 36 questions and 12 Listening passages / 36 questions / 12 neural-audio files across ILR 0–3.
- Independent chance-aware Bayesian Reading and Listening working-band estimates with passage/testlet dependence discounted.
- Conservative adjacent-band routing: after each passage the delivery band may move up or down by at most one ILR half-level based on posterior boundary probability.
- Hard Training/Diagnostic ILR floor and ceiling controls, including true ILR 2–3-only eligibility (2, 2+, and 3).
- Diagnostic boundary probes and stopping rules that require evidence at the current band and at least one adjacent band.
- Posterior uncertainty and evidence-aware practice reports.
- Information-based selection with topic, genre, question-type, and exposure balancing.
- Meaningful Training target-level bias.
- Variable bundles: Reading 1–5 questions and Listening 1–3 questions.
- Strict Simulation timing, automatic section expiry, locked navigation, and browser-confirmed one-play Listening.
- Session checkpoints, recovery, optional history, and JSON/CSV export.
- Typed Pydantic bank, session, generation, validation, and reporting models.
- Provider-independent starter content.
- One durable generated repository with separate language + skill indexes, language-specific topics, and strict Listening-audio integrity.
- Optional staged live generation with repair, quarantine, persistence, quota protection, and bank fallback.
- Immediate visible loading feedback with an accessible spinner, busy button labels, and staged progress for slow operations.
- Python-side answer shuffling and key remapping; prompts never prescribe answer letters.
- Starter answer sets rebalanced for comparable length/specificity, with automated length-pattern repair for newly generated bundles.

## Modes

### Training Mode

- Reading, Listening, or separate Reading + Listening sections.
- Starting and target ILR bands.
- Selectable lowest and highest eligible ILR bands.
- Visible next-passage routing band after answers are locked.
- Topic and comprehension-competency emphasis.
- Optional hints and passage-level review.
- Listening replay, optional voice/speed variants, and post-answer transcript review.
- Bank-only or Fresh-AI-preferred content.

### Adaptive Diagnostic

- Independent Reading and Listening posteriors.
- Broad medium prior by default, with an optional selected-band challenge start.
- Hard ILR floor/ceiling filtering when a range-limited diagnostic is requested.
- One-half-level-at-a-time passage routing from Bayesian posterior boundary probability.
- Adjacent-band evidence probes before confidence-based stopping.
- End-only feedback.
- No learner-selected slow audio or voice changes.
- Minimum evidence plus confidence-aware stopping.
- Provider/loading time is excluded from the assessment timer.

### DLPT-style Adaptive Practice Simulation

- Reading and Listening run as separate sections.
- Medium-difficulty opening passage.
- Passage difficulty adapts after every completed bundle while the active routing calculation remains hidden.
- No skipping, back navigation, or answer changes after passage submission.
- All questions in the bundle must be answered before advancing.
- Strict 30-minute shortened or up-to-three-hour standard countdown timer that ends the section automatically at zero.
- Shortened practice is clearly labeled; standard practice targets 35 questions per selected skill without an unsupported 60-question promise.
- One controlled Listening play, counted only after the browser confirms that sound actually started; no replay and no transcript during the active simulation.

See `docs/ADAPTIVE_ROUTING.md` for the routing equations, range behavior, stopping rule, and worked ILR 3 → 2+ → 2 example.

## Starter and generated item banks

The repository ships with:

- 51 starter passages: 24 Reading and 27 Listening;
- 160 starter questions: 84 Reading and 76 Listening;
- 27 bundled Listening audio assets;
- Russian: 27 passages / 88 questions / 15 audio assets;
- Mandarin: 24 passages / 72 questions / 12 audio assets;
- balanced starter keys: A=40, B=40, C=40, D=40 before session shuffling.

Immutable starter bank:

```text
data/starter_items.jsonl
data/mandarin_starter_items.jsonl
```

Runtime generated overlay (created automatically; it is intentionally not shipped as a blank release file):

```text
storage/item_bank/generated_items.jsonl
```

Generated-bank health manifest:

```text
storage/item_bank/generated_items.meta.json
```

With `PERSISTENT_STORAGE_PATH=/data`:

```text
/data/item_bank/generated_items.jsonl
/data/item_bank/generated_items.meta.json
```

Every accepted bundle is atomically committed with its passage, questions, shuffled/remapped answer keys, rationales, target-language evidence, validation reports, generation metadata, and Listening audio metadata. The same objects are inserted into the in-memory indexes immediately, so they are eligible for later fallback selection without restarting the app. The manifest records checksum and counts after every write.

On a Hugging Face Space, the application now attempts to create a private Dataset bank automatically when `HF_BANK_TOKEN` or `HF_TOKEN` has repository write permission. The default derived name is based on the Space identity, for example `alsubij/DLPT-Trainer-dlpt-generated-bank`. Accepted items are uploaded after every successful bundle and restored before the operational bank loads on the next startup.

The setup screen also provides **Download Generated Bank Backup** and **Import and Merge Backup** controls. The portable ZIP includes the JSONL records, manifest, and generated Listening MP3 files.

The starter file and generated overlay form one durable physical repository, but the application builds **separate logical Reading and Listening indexes**:

```text
Reading index: passages + questions + Reading topics
Listening index: passages + questions + Listening topics + validated audio assets
```

Reading records never require or receive audio. A Reading bundle is rejected if it references an audio asset, duration, or voice metadata. A Listening bundle is operational only when its referenced audio asset exists, is validated, matches the transcript hash, and points to a non-empty audio file.

The setup status reports Reading and Listening counts separately, including operational Listening audio health and ILR question coverage. Topic choices update when the selected skill changes. Same-skill duplicates are rejected; a deliberate cross-skill transformation may be stored with relationship metadata, while repeat exposure to the same content is suppressed across skills.

Failed candidates are written under `storage/quarantine/` or `/data/quarantine/` and never become selectable. Malformed generated-overlay records are excluded without disabling the immutable starter bank.

All starter and generated difficulty values remain **provisional** until empirical calibration exists. See `docs/SKILL_SEPARATED_BANK.md` for the storage/index/audio contract.

## GenAI authoring pipeline

A fresh bundle uses separate controlled stages:

1. Target-language passage/transcript authoring.
2. Deterministic passage checks.
3. Independent passage naturalness/level audit.
4. Bounded passage repair when needed.
5. Separate English question/choice authoring.
6. Deterministic question and distractor checks, including within-item and bundle-level answer-length cue detection.
7. Blind verification with choices reordered and the proposed answer hidden.
8. Optional second verifier for higher-risk ILR 2+/3 items.
9. Bounded question-set repair when needed.
10. Python choice shuffling, correct-key remapping, and bank-position balancing.
11. Listening TTS creation and validation.
12. Atomic generated-bank persistence or redacted quarantine.

Provider responses prefer strict JSON Schema, then best-effort schema, then JSON-object mode. When a hosted route rejects all structured-output modes, an optional controlled plain-JSON fallback accepts only one complete JSON document (or one fenced JSON document); it never extracts the first apparent `{...}` substring from arbitrary prose. Every result must still pass strict Pydantic validation.

Provider failover is round-robin by output strength: each configured provider gets a strict-schema attempt before either provider consumes weaker modes. Blind verification is batched per passage bundle, so a normal Reading generation can complete with passage authoring, passage audit, question authoring, and one independent verification request instead of one verifier request per question.

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

For the recommended no-cost routing, add Gemini and Groq keys to `.env`:

```text
ENABLE_USER_GENERATION=true
GENERATION_PROVIDER=gemini_then_groq
VERIFICATION_PROVIDER=auto
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key
ENABLE_HF_INFERENCE=false
```

A single matching generation key is enough to enable Fresh AI; using both Gemini and Groq is strongly recommended because it provides independent author/verifier routing and better quota resilience. Hugging Face bank persistence is configured separately with `HF_BANK_TOKEN` (preferred) or the backwards-compatible `HF_TOKEN`.

Current defaults:

```text
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_VERIFIER_MODEL=gemini-3.1-flash-lite
GROQ_MODEL=openai/gpt-oss-120b
GROQ_VERIFIER_MODEL=openai/gpt-oss-20b
HF_PROVIDER=auto
HF_TEXT_MODEL=openai/gpt-oss-120b
HF_VERIFIER_MODEL=openai/gpt-oss-20b
ENABLE_HF_INFERENCE=false
PREFER_GEMINI_IF_AVAILABLE=true
STRUCTURED_OUTPUT_MODE=auto
```

Original configuration remains compatible:

```text
GENAI_PROVIDER=gemini_then_groq
GEMINI_MODEL=gemini-3.1-flash-lite
GROQ_MODEL=your_supported_model
# Optional legacy HF inference route:
HF_PROVIDER=auto
HF_TEXT_MODEL=your_supported_model
```

Do not set both `GENERATION_PROVIDER` and `GENAI_PROVIDER` to conflicting values.

### Cost, retry, and quality controls

```text
MAX_GENERATION_REQUESTS_PER_SESSION=8
GENERATION_CONCURRENCY_LIMIT=1
PROVIDER_TIMEOUT_SECONDS=45
PROVIDER_MAX_RETRIES=1
MAX_PROVIDER_ATTEMPTS_PER_STAGE=4
GENERATION_AUDIT_MODE=always
GENERATION_REPAIR_ATTEMPTS=2
SECOND_VERIFIER_HIGH_RISK=true
AUTHORING_TEMPERATURE=0.25
VERIFICATION_TEMPERATURE=0.0
PASSAGE_MAX_TOKENS=3200
QUESTION_MAX_TOKENS=2600
REPAIR_MAX_TOKENS=3200
AUDIT_MAX_TOKENS=1200
VERIFIER_MAX_TOKENS=2400
```

Configured token values are hard caps. The application applies smaller stage-, level-, and bundle-aware budgets when appropriate. `ALLOW_PLAIN_JSON_FALLBACK=true` enables the controlled complete-document fallback described above. `GENERATION_DIAGNOSTICS=true` writes sanitized provider/stage/mode/model diagnostics to the Space container log without printing secret values or full prompts.

`GENERATION_AUDIT_MODE=smart` saves one audit call only for lower-risk Reading Training content. Diagnostic, Simulation, Listening, ILR 2+, and ILR 3 continue to receive the passage audit. `off` is supported but produces a startup warning.

## Hugging Face Spaces deployment

1. Create a **Gradio** Space.
2. Extract the release ZIP on your computer. Open the extracted folder, select **all files and folders inside it**, and upload those contents to the Space root. Do not upload only the ZIP file, and do not upload the enclosing folder as a nested directory.
3. In the Space **Files** tab, confirm that `README.md`, `app.py`, and `requirements.txt` appear at the top level. The app will not configure or start if they appear inside another folder.
4. The starter bank launches without secrets.
5. Add provider secrets in **Settings → Variables and secrets** to enable Fresh AI.
6. Attach persistent storage and set `PERSISTENT_STORAGE_PATH=/data` to retain generated items across rebuilds.
7. Run a short Training session and the smoke test after deployment.

### Required Space secrets

None for bank-only operation.

### Fresh-AI secrets

Recommended:

```text
GEMINI_API_KEY
GROQ_API_KEY
```

`GEMINI_API_KEY` is the primary authoring route and `GROQ_API_KEY` provides independent verification/fallback. Fresh AI can still operate with only one of them, but two-provider routing is more reliable. Use `HF_BANK_TOKEN` separately for durable private Dataset persistence.

### Recommended Space variables

```text
ENABLE_USER_GENERATION=true
GENERATION_PROVIDER=gemini_then_groq
VERIFICATION_PROVIDER=auto
ENABLE_HF_INFERENCE=false
PREFER_GEMINI_IF_AVAILABLE=true
STRUCTURED_OUTPUT_MODE=auto
GENERATION_AUDIT_MODE=always
GENERATION_REPAIR_ATTEMPTS=2
SECOND_VERIFIER_HIGH_RISK=true
MAX_GENERATION_REQUESTS_PER_SESSION=8
GENERATION_CONCURRENCY_LIMIT=1
PROVIDER_TIMEOUT_SECONDS=45
PROVIDER_MAX_RETRIES=1
MAX_PROVIDER_ATTEMPTS_PER_STAGE=4
QUEUE_CONCURRENCY_LIMIT=4
ALLOW_PLAIN_JSON_FALLBACK=true
GENERATION_DIAGNOSTICS=true
VERIFIER_MAX_TOKENS=2400
LOG_LEVEL=INFO
ENABLE_HISTORY=true
ENABLE_ANALYTICS=false
CHECKPOINT_AFTER_PASSAGE=true
PERSISTENT_STORAGE_PATH=/data
# Recommended free/private Dataset durability:
HF_BANK_TOKEN=<write-capable Space secret>
AUTO_PROVISION_DATASET_BANK=true
# Optional explicit repository instead of the derived private name:
HF_DATASET_REPO=your-username/dlpt-generated-bank
STORAGE_BACKEND=hybrid
HF_DATASET_PRIVATE=true
SYNC_GENERATED_BANK_ON_STARTUP=true
SYNC_GENERATED_BANK_ON_WRITE=true
BANK_SYNC_MAX_RETRIES=3
```

When `HF_DATASET_REPO` is set, the app selects `hybrid` automatically unless another backend is explicitly requested. On Spaces, `AUTO_PROVISION_DATASET_BANK=true` also selects hybrid persistence when `HF_BANK_TOKEN` or `HF_TOKEN` is present. `HF_BANK_TOKEN` is preferred so bank-write permission remains separate from inference access. Accepted Listening MP3s are mirrored under `audio/` together with the JSONL bank and health manifest.

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

Default Space disk is ephemeral. Without durable storage, accepted generated items are atomically saved, indexed, and reusable immediately, but they disappear after the container is replaced.

Three protection layers are implemented:

1. **Mounted storage:** set `PERSISTENT_STORAGE_PATH=/data`. Generated items, manifest, audio, checkpoints, history, quarantine records, and exports use the mounted volume.
2. **Automatic private Hugging Face Dataset:** add a write-capable `HF_BANK_TOKEN` secret and leave `AUTO_PROVISION_DATASET_BANK=true`. The app derives/creates a private Dataset, restores it at startup, and uploads after every accepted bundle. `HF_TOKEN` is used as a backwards-compatible fallback when it already has write permission.
3. **Explicit Dataset mirror:** set `HF_DATASET_REPO` and `STORAGE_BACKEND=hybrid` or `hf_dataset` when you want to control the exact repository name.

Regardless of backend, the UI can export a portable bank ZIP and import/merge it later. Release archives omit blank generated-bank runtime files, so copying new source folders cannot overwrite an existing mounted or restored bank.

The setup screen shows the current generated passage/question counts, checksum prefix, and persistence mode. Active session status updates those counts after live generation. If remote synchronization fails, the local atomic commit remains usable and the UI states that the item is not yet durably mirrored.

The application checkpoints after each submitted passage. Provider failure does not delete completed responses, and generation/loading time is added back to active timer anchors. See `docs/BANK_PERSISTENCE_AND_LOADING.md` for the full commit and recovery flow.

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

- the session content source is **Fresh AI preferred** rather than **Validated bank only**;
- `ENABLE_USER_GENERATION=true`;
- a supported `GENERATION_PROVIDER` is selected;
- a matching secret exists;
- the configured model is available to the selected provider;
- quota/rate limits are available;
- `MAX_GENERATION_REQUESTS_PER_SESSION` is above zero;
- the candidate is not being rejected by validation or duplicate checks.

For optional Hugging Face generation (`ENABLE_HF_INFERENCE=true`), the token must be authorized to make Inference Providers calls. A repository token can remain perfectly valid for the generated-bank Dataset while hosted HF inference is unavailable or out of monthly credits.

The active-session banner now distinguishes:

- `Fresh AI bundle generated, validated, saved, and selected`; or
- `Fresh AI fallback`, followed by the sanitized reason.

With `GENERATION_DIAGNOSTICS=true` and `LOG_LEVEL=INFO`, the container log records safe lines such as `GenAI request`, `GenAI attempt failed`, `Fresh bundle accepted`, and `Fresh generation failed; using bank fallback`. It records stage, provider, model, output mode, and attempt number, but never the API key or full secret-bearing environment. Quarantine records include stage traces and redacted failure reasons.

The pipeline tries configured providers fairly at each output strength, supports controlled complete-document JSON fallback, and performs one batched blind-verification call per bundle. This reduces silent failures caused by exhausting all attempts on one provider or making one remote verification request per question.

### Generated items disappear after restart

The setup banner must say **restart-safe**. If it says `NOT restart-safe — ephemeral local Space storage`, add this Space secret:

```text
HF_BANK_TOKEN=<a Hugging Face token with repository write permission>
```

Keep these variables:

```text
AUTO_PROVISION_DATASET_BANK=true
SYNC_GENERATED_BANK_ON_STARTUP=true
SYNC_GENERATED_BANK_ON_WRITE=true
BANK_SYNC_MAX_RETRIES=3
```

The next startup creates or restores a private Dataset automatically. An explicit repository remains supported:

```text
PERSISTENT_STORAGE_PATH=/data
```

or:

```text
HF_DATASET_REPO=your-username/dlpt-generated-bank
STORAGE_BACKEND=hybrid
HF_BANK_TOKEN=<write-capable Space secret>
SYNC_GENERATED_BANK_ON_STARTUP=true
SYNC_GENERATED_BANK_ON_WRITE=true
BANK_SYNC_MAX_RETRIES=3
```

The setup banner identifies whether the current bank is ephemeral, mounted, or Dataset-synchronized. Use **Download Generated Bank Backup** before any update whenever the banner is not restart-safe.

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

### Reading session fails with `Value: 'G'` or `Value: 'C'`

Version 1.2.5 fixes a Gradio CheckboxGroup payload edge case. A single selected topic such as `Government and politics` could be submitted as one scalar string, then incorrectly validated character-by-character as `G`. Topics and competencies now normalize scalar selections into one-item lists before validation, with a second allow-list check inside the session callback.

### Session interrupted

Use the displayed recovery code under **Recover a Checkpoint**. A corrupted checkpoint is rejected safely.

## v1.2.8 verifier evidence correction

A fresh bundle can now remain operational when the blind verifier selects the same answer and confirms sufficient evidence but paraphrases its Russian support quote. The question author's `evidence_ru` remains a strict exact-substring requirement; that is the evidence shown in review and stored in the bank. The verifier's separate quote is now recorded as an advisory exactness/traceability score rather than acting as a duplicate brittle hard gate.

This specifically fixes the runtime fallback reason `q1:verifier_evidence_not_in_passage`. It does not weaken answer agreement, ambiguity, outside-knowledge, insufficient-evidence, reasoning-level, answer-leakage, or confidence checks. See `docs/VERIFIER_EVIDENCE_RUNTIME_FIX.md`.

## v1.2.7 hosted question-schema correction

The container log can show successful passage authoring and auditing followed by repeated `CandidateQuestionSet: ValidationError` failures. That was a local schema-contract bug, not an invalid API key and not a provider outage. The older provider schema advertised `question_type` and `target_ilr` as arbitrary strings while Python later required exact values, and it unnecessarily required the model to reproduce internal difficulty metadata.

Version 1.2.7 introduced a smaller provider-facing question contract with an explicit question-type enum. The provider returns only the English stem, four English choices, zero-based proposed answer index, English rationale, short target-language evidence, and one supported question type. Python assigns the requested ILR, derives provisional difficulty, shuffles choices, remaps the answer key, validates the bundle, and saves accepted content to the reusable bank.

The parser also accepts safe common variants such as `items` instead of `questions`, A/B/C/D choice dictionaries, `correct_answer: "A"`, `detail` instead of `prominent detail`, and extra provider metadata. It does not silently accept unsupported or incomplete questions: those proceed to deterministic validation and targeted repair, or are quarantined.

When a provider payload still fails, the error now identifies exact locations such as `questions.0.choices` rather than reporting only the generic word `ValidationError`. See `docs/QUESTION_SCHEMA_RUNTIME_FIX.md`.

## v1.2.6 GenAI runtime correction

This release fixes the production Fresh-AI path for both Reading and Listening. The earlier pipeline was thoroughly tested with deterministic providers but could silently fall back in a real Space after spending its stage-attempt budget on one provider's structured-output modes and then making several sequential verification calls. Version 1.2.6 uses fair cross-provider mode ordering, controlled whole-document JSON fallback, batched blind verification, larger verifier budgets, tolerant audit-flag handling, visible generated-versus-fallback status, and sanitized stage diagnostics. The bank-only path remains available and every accepted fresh bundle is still validated, atomically committed, indexed immediately, and eligible for fallback.

The recurring `BaseEventLoop.__del__` / `Invalid file descriptor: -1` startup lines are not the generation result. When the log reaches `Running on local URL`, inspect the later `dlpt.genai` lines and the in-app Fresh AI banner to determine whether generation was accepted or why it fell back.

See `docs/GENAI_RUNTIME_FIX.md` for the detailed failure analysis and verification.

## Repository structure

```text
app.py
core/
  adaptive.py
  audio.py
  bank_persistence.py
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
  components.py
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


## v1.2.9 item-level disclosure

The application reveals item levels only at feedback-safe points:

- Training with passage feedback: each completed question shows its intended ILR band.
- Training with end-only feedback: levels appear in the final report.
- Adaptive Diagnostic and DLPT-style Adaptive Practice Simulation: levels remain hidden during the active test and appear only after completion.

Uncalibrated items are labeled as an **intended provisional ILR level**. When empirical calibration exists, the report shows the approximate calibrated operational band and separately preserves the original authoring target. These are practice metadata, not official DLPT item classifications.

### Troubleshooting answer selection and bank synchronization

Version 1.3.2 fixes a Gradio 6 dynamic-Radio issue that could reject `A`, `B`, `C`, or `D` because the server retained an empty original choice list. Answer keys are now stable on both the browser and server.

When the reusable-bank banner reports a failed Dataset synchronization, open **Generated Bank Backup & Persistence** and press **Test / Retry Durable Bank Sync**. The status and container log now show a sanitized HTTP reason. Confirm that `HF_BANK_TOKEN` is a Hugging Face user access token with repository write permission and that it can create or edit the configured private Dataset. The app tries `HF_TOKEN` as a fallback when it differs from `HF_BANK_TOKEN`.


### Troubleshooting Fresh Listening generation

Version 1.3.3 distinguishes three separate failure stages:

- **Question validation failed before audio creation:** the generated passage was usable, but one or more English questions or distractors failed quality checks. The app now repairs only the failed question positions for up to two bounded passes before using the bank.
- **Listening audio generation failed:** the passage and questions passed, but Edge TTS could not create the MP3. The session is preserved and a validated bank item is selected.
- **Generated Listening audio failed validation:** an MP3 was created but was empty, incomplete, or outside the operational duration range.
- **Level 3 Listening requested a duration repair:** the first transcript rendered below 2:00 or above 2:30. The app now measures the real cached MP3 before writing questions and asks the authoring model to repair the transcript while preserving natural sentence boundaries. Mandarin Level 3 targets 520-650 Chinese characters as guidance, but the measured audio duration is authoritative.

A message such as `q2:no_near_duplicate_choices` is therefore a question-quality rejection, not an audio failure. The generated bank and Dataset synchronization remain intact.


## Natural listening speech

Version 1.6.0 keeps the no-cost Edge TTS backend and improves generated Russian and Mandarin listening audio through conservative text phrasing, passage-aware voice selection, and small deterministic rate/pitch adjustments. Previously saved AI passages are upgraded lazily when played and then cached, so startup remains fast. The app does not claim human-recorded audio; generated recordings remain synthetic practice material.



## v1.7.4 runtime repair

This historical v1.7.4 section describes the runtime repair that broadened dialogue-role detection so role labels such as seller/buyer are removed before TTS and receive distinct voices. Current v1.7.8 routing instead defaults to Gemini 3.1 Flash-Lite, with live model discovery and Groq retained for independent verification/failover.
