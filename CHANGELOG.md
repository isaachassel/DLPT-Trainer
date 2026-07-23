# Changelog

## Phase 0 — Stabilize

- Preserved the submitted source in `backup/original_v3_3_source.zip`.
- Pinned all dependencies and aligned README Space metadata with Gradio 6.5.1.
- Added complete `.env.example` with no real keys.
- Removed fixed answer-letter patterns from operational authoring prompts.
- Added code-side shuffling and correct-key remapping.
- Added audio validation and age/reference-aware cleanup utilities.
- Added deterministic mock/provider facilities and recoverable provider errors.
- Added checkpoint preservation and duplicate-request nonce handling.

## Phase 1 — Core architecture

- Replaced dataclasses with strict Pydantic models.
- Added item-bank, storage, validation, generation, audio, session, scoring, and reporting modules.
- Added mixed-record JSONL starter bank with passages, questions, audio assets, and validation reports.
- Added deterministic validation and item quarantine workflow.
- Added blind-answer verification architecture.
- Added local/mounted storage abstraction and safe exports.

## Phase 2 — Real adaptation

- Implemented separate Bayesian Rasch/1PL posteriors for Reading and Listening.
- Added EAP ability, posterior standard error, 80% intervals, confidence categories, and predicted success by ILR band.
- Added information-based selection near current ability.
- Added Training target-level bias.
- Added topic, genre, question-type, and exposure balancing.
- Added session and profile no-repeat controls.
- Added confidence-aware diagnostic stopping and insufficient-evidence reporting.

## Phase 3 — Mode-accurate UX

- Added distinct Training, Diagnostic, and Full CA Simulation setup and behavior.
- Added mode-specific control hiding.
- Added strict countdown and standard count-up timers with server-side expiration checks.
- Added variable 1–5 Reading and 1–3 Listening bundles.
- Added one-passage-at-a-time locked progression.
- Added one controlled Listening play in strict modes and replay through a tracked button in Training.
- Added English context orientation before every passage.
- Added progress, loading/error status, hints, transcript rules, and interruption recovery.
- Added confirmed abandonment for strict sessions and partial stopping for Training.

## Phase 4 — Reporting and persistence

- Added separate Reading and Listening reports.
- Added uncertainty, evidence quantity, grouped accuracy, response timing, playback count, strengths, weaknesses, review evidence, and next-session recommendations.
- Added JSON and CSV export.
- Added optional local profile history and exposure control.
- Added checkpoint checksum validation and safe corruption handling.

## Phase 5 — QA and deployment

- Added 46 automated tests.
- Added item-bank validation, Space smoke test, and 35-question end-to-end Reading/Listening simulations.
- Added Hugging Face deployment, secrets, variables, troubleshooting, restart, and persistence documentation.
- Added known limitations and future calibration guidance.

## v1.1 — Hybrid live-generation restoration

### Content architecture correction

- Restored user-selectable live AI passage generation instead of limiting generation to offline administration.
- Added two explicit content policies: validated bank only and Fresh AI preferred with automatic bank fallback.
- Loaded the immutable starter bank and writable generated-bank overlay as one indexed operational bank.
- Accepted generated items become selectable immediately and remain available to later sessions.
- Added mounted-volume routing so generated items, audio, quarantine records, sessions, and history can survive Space restarts when `/data` is configured.

### Controlled generation and validation

- Added a constrained live-generation service with provider retries, provider fallback, concurrency limiting, and per-session bundle limits.
- Added adaptive requested-level selection using the active skill posterior and Training target-level bias.
- Added blind answer verification before answer-position shuffling.
- Added Python-side shuffling, key remapping, and deterministic revalidation before persistence.
- Added duplicate and near-duplicate rejection against both starter and previously generated content.
- Added automatic Listening TTS generation, duration/file validation, content-hash caching, and bank-linked audio metadata.
- Added atomic persistence of passages, questions, validation reports, and audio assets.
- Added quarantine records for schema, provider, validation, duplicate, and audio failures.
- Kept failed content out of all operational sessions.

### Session reliability and UX

- Added a visible content-source control and provider-readiness banner.
- Added generation, acceptance, fallback, and quota status to the active session display and final report.
- Excluded provider/loading time from standard and strict testing timers.
- Preserved checkpoints and completed responses when fresh generation fails.
- Added previously generated bank items to normal adaptive selection and exposure control.
- Updated administrator generation scripts to use the same validated persistence pipeline.

### QA

- Expanded the automated suite from 46 to 51 tests.
- Added tests for live generation, atomic generated-bank persistence, reloadability, answer-shuffle metadata, duplicate quarantine, unavailable-provider fallback, and generation-limit fallback.

## v1.2 — GenAI/API and prompt pipeline overhaul

### API compatibility and security

- Confirmed the original source contained provider environment references, not committed secret values.
- Preserved `HF_TOKEN`, `GROQ_API_KEY`, `HF_PROVIDER`, `HF_TEXT_MODEL`, and `GROQ_MODEL` behavior.
- Restored legacy `GENAI_PROVIDER` as an alias while keeping `GENERATION_PROVIDER` as the preferred setting.
- Added independent `VERIFICATION_PROVIDER`, `HF_VERIFIER_MODEL`, and `GROQ_VERIFIER_MODEL` controls.
- Excluded secret fields from `Settings` serialization and representation.
- Added recursive secret redaction at quarantine persistence, not only in caller-created error strings.
- Added startup warnings for weaker JSON-object-only mode, disabled passage audit, same-model author/verifier configuration, and deprecated model settings.

### Prompt and content-authoring architecture

- Replaced the compressed all-in-one v1.1 prompt with `core/prompts.py` and a staged pipeline.
- Restored useful level-specific Reading/Listening discourse, genre, reasoning, and natural-language guidance from the original concept.
- Removed fixed answer-letter examples and all dependence on model-side answer randomization.
- Reframed word count as soft guidance while enforcing hard simulation limits and discourse-quality gates.
- Split passage authoring, passage audit, passage repair, question authoring, question repair, and blind answer verification into separate schemas and prompts.
- Added controlled novelty context from the current bank without exposing user-authored arbitrary prompts.

### Structured output and independent validation

- Added provider-enforced strict JSON Schema as the first output mode.
- Added best-effort schema and JSON-object fallbacks for model/provider compatibility.
- Kept strict Pydantic validation after every provider response.
- Added independent passage naturalness/coherence/level audit.
- Added blind verification with randomized choice order and no proposed key.
- Added optional second verification for higher-risk ILR 2+/3 item types.
- Added bounded passage and question repair passes based on explicit deterministic/verifier failures.
- Strengthened deterministic passage and question validation for language, repetition, n-grams, markup artifacts, evidence, answer leakage, choice similarity, orientation leakage, status, linkage, and bundle constraints.

### Cost, reliability, and analytics

- Added stage-, level-, and bundle-aware token budgets beneath configured hard caps.
- Added maximum outbound provider attempts per structured-output stage.
- Implemented meaningful `GENERATION_AUDIT_MODE=smart` behavior.
- Counted failed as well as successful provider calls.
- Attached failed call/repair counts to generation errors so fallback sessions preserve accurate analytics.
- Stored provider/model, verifier/provider, prompt version, pipeline version, calls, repairs, and provider-reported token usage in generated item metadata.
- Updated user-facing generation status with author, verifier, call, and repair information.
- Updated Groq and Edge TTS pins and migrated default Groq models.

### QA and documentation

- Expanded the suite from 51 to 63 tests.
- Added tests for fixed-answer-pattern absence, hidden proposed keys, separate author/verifier stages, strict schema-first calls, legacy environment compatibility, repair persistence, smart audit behavior, provider-attempt caps, failed-call analytics, quarantine redaction, and secret-excluding settings serialization.
- Added `docs/GENAI_AUDIT.md` and rewrote provider/prompt setup documentation.
- Regenerated all Pydantic JSON schemas.
