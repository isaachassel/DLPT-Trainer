# Changelog

## 1.6.0 — Natural Listening Prosody

- Kept the free Microsoft Edge TTS engine while replacing flat one-profile synthesis with restrained passage-aware prosody.
- Added deterministic Russian voice selection between Svetlana and Dmitry based on passage genre and topic.
- Added subtle, bounded speaking-rate and pitch variation so recordings do not all share identical cadence.
- Added conservative spoken-text preparation that repairs punctuation spacing, inserts natural pauses after Russian discourse markers, and creates paragraph-level breathing resets without changing tested words or meaning.
- Invalidated the old generated-audio cache so newly authored listening passages use the natural-v2 rendering.
- Lazily upgrades older saved AI audio only when selected, then caches it, avoiding mass regeneration and slow startup.
- Applies natural spoken phrasing to user-selected Training voices and speeds.
- Added regression coverage for phrasing, deterministic voice/prosody selection, parameter bounds, and cache-key separation.

## 1.5.2 — Reliable Listening Playback and Faster Restarts

- Replaced blocked autoplay-only Listening behavior with an explicit browser audio play control.
- Strict modes hide controls immediately after browser-confirmed playback begins, preserving one-play behavior without making first playback impossible.
- Changed audio preloading from full-file autoplay to metadata-only loading, reducing delay and bandwidth.
- Reused Hugging Face Hub cache entries during generated-bank restoration instead of forcing every audio file to download again.
- Kept browser-confirmed play counting and checkpoint safety intact.

## v1.5.1 — Never-stop generated-question recovery

- When targeted question repair is exhausted, discards the flawed set and authors a completely fresh question set for the already-validated passage.
- Keeps the answer-length anti-clue guard; it no longer interrupts the learner merely because one AI draft fails that guard.
- Preserves the active session and selects a validated saved item if both fresh question sets fail or the provider is unavailable.
- Keeps internal validator codes in server logs/quarantine instead of exposing them as learner-facing errors.
- Adds regression coverage for full question-set regeneration and sanitized recovery messaging.

## v1.5.0 — Measurement, content, timing, and bilingual release hardening

- Keeps Fresh AI available in Training, Diagnostic, and Simulation without adding a human-vetting gate.
- Rewrites 86 built-in answer sets for more parallel length and specificity; the former longest-choice strategy drops from roughly 55–71% to 14–19%, with zero materially keyed length outliers under the new audit.
- Adds within-item and bundle-level answer-length cue detection and targeted repair for future generated items.
- Replaces the provisional 1PL likelihood with a transparent four-choice chance floor and discounts same-passage testlet dependence so uncertainty does not shrink unrealistically.
- Reports a provisional working band rather than implying an official score or DLPT prediction.
- Records actual final-selection latency per question instead of dividing passage time equally.
- Withholds topic/genre/competency-specific recommendations until a skill has at least eight completed questions.
- Counts strict Listening playback only after the browser confirms audio started, so blocked autoplay no longer consumes the learner's one play.
- Automatically closes strict sections at zero and scores a fully answered passage only when every final selection occurred before the deadline.
- Renames the strict mode to **DLPT-style Adaptive Practice Simulation**, replaces the unsupported 60-question option with a documented 35-question standard practice option, and uses up to three hours per selected skill.
- Uses Traditional characters in half of the bundled ILR 2+/3 Mandarin Reading passages and alternates Simplified/Traditional instructions for future high-level generated Reading.
- Replaces all 72 generic Mandarin rationales with evidence-, competency-, and distractor-specific explanations.
- Prevents generated overlays from overwriting or attaching questions to built-in IDs.
- Adds compressed size, expanded size, member count, per-file size, encryption, and compression-ratio limits to bank imports, followed by complete deterministic bank validation before commit.
- Makes the release validator and smoke test cover both languages: 51 passages, 160 questions, and 27 audio assets.
- Hides raw Gradio tracebacks in production and expands regression coverage to 156 passing tests.

## v1.4.3 — Mandarin Level 3 sustained-listening duration repair

- Measures Mandarin sentence length in Chinese characters instead of whitespace-oriented tokens.
- Targets 520-650 Chinese characters for Level 3 Mandarin listening and natural sentence boundaries.
- Synthesizes a cached audio preview before question authoring, measures its real duration, and automatically repairs passages outside the 120-150 second target.
- Reuses the accepted cached preview for the final listening asset so the duration check does not create duplicate TTS work.

## v1.4.2 — Mandarin Level 3 generation audit repair

- Replaced the Russian-only passage-audit contract field `natural_russian` with the language-neutral `natural_target_language`.
- Made audit rejection diagnostics language-specific, so Mandarin candidates can report `unnatural_mandarin` rather than the misleading Russian-only failure.
- Clarified the independent verifier prompt to evaluate Mandarin as Mandarin rather than against Russian language criteria.
- Strengthened Mandarin repair instructions with a level- and skill-specific Chinese-character range, requiring coherent discourse development rather than filler when a Level 3 passage is too short.
- Added a regression test to prevent Mandarin audits from emitting Russian-specific diagnostics.

## v1.4.1 — Hugging Face root-package repair

- Rebuilt the distribution as a root-flat Space package so `README.md`, `app.py`, and `requirements.txt` are placed at the repository root instead of under an extra enclosing directory.
- Quoted the Space title in the YAML front matter for unambiguous metadata parsing.
- Added explicit deployment checks that prevent uploading only the ZIP or nesting the extracted project folder inside the Space.

## v1.4.0 — Mandarin Reading and Listening

- Added a Russian/Mandarin language selector while retaining every existing Russian workflow.
- Added language + skill bank isolation so Russian and Mandarin passages, questions, topics, exposure history, and adaptive selection cannot mix.
- Added 12 Mandarin Reading and 12 Mandarin Listening starter passages, with 36 questions per skill and full ILR 0–3 coverage.
- Bundled validated Mandarin neural audio for every starter Listening passage.
- Added Mandarin-specific generation, repair, audit, blind-verification, script validation, character counting, hashing, duplicate detection, evidence tracing, and TTS voice routing.
- Added Xiaoxiao/Yunxi training voices and language-specific generated-listening defaults.
- Added multilingual reporting and language-tagged response exports.
- Expanded regression coverage to 139 passing tests, including cross-language bank isolation, Mandarin audio integrity, and Mandarin live-generation materialization.

## v1.3.5 — Bank terminology and no-write guarantee

- Replaced ambiguous “operational” UI wording with **Ready to use now (starter + saved AI)**.
- Split every skill summary into built-in starter, saved AI-generated, and ready-to-use totals.
- Clarified that ILR coverage is for the ready-to-use pool.
- Added explicit bank-only session messaging that no content is generated or written.
- Relabeled startup restoration as a launch-time snapshot so later Fresh-AI growth is not mistaken for a bank-only write.
- Added source-aware bank health metrics and regression coverage proving bank-only selection leaves the generated JSONL byte-for-byte unchanged.

## v1.3.4 — Skill-Separated Bank Indexing and Audio Integrity

### Logical Reading and Listening banks
- Keeps one durable JSONL/Dataset repository while building separate in-memory Reading and Listening passage, question, topic, and ILR indexes.
- Reading selection can only use Reading records; Listening selection can only use operational Listening records with validated audio.
- Reusable-bank status now reports Reading and Listening counts separately instead of presenting one ambiguous total.
- Active-session content status shows the generated bank for the current skill only.

### Audio integrity
- Reading bundles are rejected if they contain an audio asset, audio duration, or voice metadata.
- Listening bundles are rejected unless the referenced audio asset exists, is validated, has a matching transcript hash, and points to a non-empty file.
- Bank validation and operational selection enforce the same skill/audio contract for restored Dataset records.

### Topics and duplicate policy
- Topic controls now update to the selected skill and preserve only still-valid selections.
- Same-skill exact and near duplicates are rejected.
- Cross-skill equivalents may be stored as explicitly related transformations, but their relationship is recorded and repeat exposure is suppressed across skills within a session/history.
- Bank health reports cross-skill related pairs rather than misclassifying them as same-skill duplicates.

### Verification
- Added regression tests for skill indexes, skill-specific topics, Reading-with-audio rejection, Listening-without-audio rejection, cross-skill relationship metadata, and separated health totals.
- Expanded the automated suite to 130 passing tests.

## v1.3.3 — Targeted Question Repair and Listening Pipeline Diagnostics

### Fresh Listening generation
- Fixed misleading Listening fallbacks where question validation failed before TTS but the user reasonably interpreted the failure as an audio problem.
- Generation errors now identify whether failure occurred during question validation, audio creation, or audio file/duration validation.
- Added explicit Listening TTS start/success diagnostics without logging transcripts or secrets.

### Question-quality recovery
- Replaced whole-bundle question regeneration with targeted repair of only the failed question positions when possible.
- Preserves the accepted passage and valid questions while replacing a failed distractor/evidence item such as `q2:no_near_duplicate_choices`.
- Increased the default bounded repair allowance from one to two passes.
- Improved the repair prompt with issue-specific instructions for materially distinct distractors and exact short Russian evidence.
- Added safe evidence-span canonicalization for verbose or punctuation-normalized model quotes; blind verification remains mandatory.
- Replaced the overly broad raw string-similarity check with a choice-specific duplicate detector that permits parallel grammar while rejecting tiny qualifier changes.

### Verification
- Added a full Listening generation integration test that begins with a defective Q2, repairs only Q2, creates a validated MP3, commits the complete bundle, and immediately reloads it from the bank.
- Expanded the automated suite to 122 passing tests.

## 1.3.2 — Answer Radio and Durable-Bank Sync Repair

### Runtime answer selection
- Fixed the production Gradio error `Value: 'B' is not in the list of choices: []`.
- Answer radios now keep stable server-side A/B/C/D values while visible labels change passage-by-passage.
- Added a strict answer-key preprocessor that accepts only A, B, C, or D even when Gradio retains stale dynamic-choice metadata.
- Recoverable submission errors now restore both the learner's selected answer and the complete visible answer choices.

### Generated-bank durability
- Validates or creates the configured private Dataset before attempting startup restore.
- Adds bounded retries with exponential backoff for transient Hub failures.
- Tries `HF_BANK_TOKEN` first and then `HF_TOKEN` when they are different, allowing recovery from a stale or under-scoped dedicated token.
- Logs sanitized HTTP status/reason information under `dlpt.persistence`; tokens are never logged.
- Displays the sanitized last synchronization error in the reusable-bank status instead of only saying that sync failed.
- Adds a **Test / Retry Durable Bank Sync** control to verify write access and push the current bank without generating another item.
- Adds `BANK_SYNC_MAX_RETRIES` configuration, defaulting to 3.

### Verification
- Added regression coverage for stale/empty Radio choices, live B-answer submission, token fallback, detailed sync errors, and manual sync behavior.

## v1.3.1 — Bayesian adjacent-band adaptive routing

- Audited the existing adaptive engine and confirmed that it updated a Bayesian Rasch posterior, but did not expose or enforce an intuitive passage-level ILR routing ladder.
- Added separate Reading and Listening routing bands and routing histories.
- Added posterior-boundary routing that moves at most one adjacent ILR half-level after each completed passage.
- Added a 67% posterior-direction threshold so one isolated wrong answer does not trigger a large difficulty collapse.
- Added hard minimum/maximum ILR eligibility controls for Training and Adaptive Diagnostic.
- Added a genuine 2–3-only range that admits only ILR 2, 2+, and 3 items.
- Added optional selected-band Diagnostic starts while retaining medium difficulty as the recommended neutral start.
- Kept Full CA Simulation at a medium opening passage and full supported range.
- Made fresh AI generation request the current routing band rather than an unrelated static target.
- Added exact-band preference and nearest-adjacent fallback in bank selection.
- Normalized bundle information so long passages do not automatically dominate shorter passages solely because they contain more questions.
- Added deterministic randomization among near-equivalent top candidates to reduce systematic item overexposure.
- Added diagnostic adjacent-band probes and required current/adjacent-band evidence before precision-based stopping.
- Added final-report routing paths, movement reasons, and range-limited interpretation warnings.
- Hid unused target controls outside Training and hid start/target controls in Full Simulation.
- Added `docs/ADAPTIVE_ROUTING.md` and new routing/range/stopping regression tests.

## v1.3.0 — Durable generated-bank protection

- Added automatic private Hugging Face Dataset provisioning for generated content.
- Added `HF_BANK_TOKEN` so bank-write permission can be separated from inference access.
- Derived a private Dataset name from the running Space identity when `HF_DATASET_REPO` is not supplied.
- Restored and merged the remote bank before the operational item bank loads.
- Mirrored accepted JSONL records, health metadata, and generated Listening audio after every successful bundle.
- Added portable ZIP export and duplicate-safe import/merge controls to the Gradio interface.
- Added in-place item-bank reload after import.
- Added explicit restart-safe versus ephemeral status messaging.
- Removed blank generated runtime-bank files from release packaging.
- Added automatic-provisioning and backup round-trip tests.


## v1.2.9 — Mode-sensitive item-level disclosure

- Added item-level disclosure to Training passage feedback.
- Added a question-by-question ILR section to every final Reading and Listening report.
- Kept item levels hidden during active Adaptive Diagnostic and Full CA Simulation sections.
- Distinguished provisional authoring targets from empirically calibrated operational difficulty.
- Added regression tests for provisional labels, calibrated labels, complete final-report coverage, Training feedback, and strict-mode non-disclosure.


## v1.2.8 — Verifier evidence-gate correction

### Confirmed runtime failure

- Fresh passage authoring, passage audit, question authoring, and blind answer selection all succeeded.
- The generated bundle was rejected only because the independent verifier paraphrased or normalized its supporting Russian quote instead of reproducing an exact contiguous substring.
- The application treated that advisory verifier quote as a second hard evidence gate, even though the operational question's own `evidence_ru` had already passed an exact-substring check against the passage.
- A repair pass repeated the same brittle rule and could reject another otherwise valid bundle before falling back to the bank.

### Validation correction

- Kept the operational question evidence check strict: `QuestionItem.evidence_ru` must still be an exact, short passage substring.
- Changed the verifier-supplied `evidence_quote_ru` from a hard acceptance gate to an advisory validation signal.
- Added `verifier_evidence_exact` and `verifier_evidence_traceability` scores to every blind-verification report.
- A verifier quote that is shortened, normalized, or paraphrased no longer discards a bundle when the verifier selected the same answer, reported sufficient evidence, and the operational evidence span is exact.
- Disagreement, ambiguity, outside knowledge, insufficient evidence, reasoning mismatch, answer leakage, and low confidence remain rejection conditions.
- Updated verifier prompts to request exact contiguous copying and to return `evidence_sufficient=false` when no exact support exists.
- Bumped the prompt/pipeline contract to `genai-pipeline-v7`.

### QA

- Expanded the suite from 93 to 96 tests.
- Added single-item and batched verifier regression coverage for paraphrased evidence.
- Added a full generation-to-persistence regression proving that a supported bundle with a paraphrased verifier quote is accepted without a repair pass.
- Added a safety regression proving that the operational question evidence still fails when it is not present in the Russian passage.
- Re-ran the full test suite, starter-bank validation, Gradio smoke test, and local HTTP launch check.

## v1.2.7 — Hosted question-schema compatibility fix

### Confirmed root cause

- Hosted passage authoring and passage audit were succeeding with HTTP 200 responses.
- Both Hugging Face and Groq then returned question JSON, but local Pydantic validation rejected `CandidateQuestionSet` before deterministic item validation could run.
- The previous JSON Schema exposed `question_type` and `target_ilr` as unconstrained strings even though custom Python validators required exact values. A provider could therefore satisfy the advertised schema with values such as `detail`, `central idea`, or `ILR 2`, then fail locally.
- The provider was also being asked to reproduce internal `target_ilr` and `provisional_difficulty` metadata that the application can derive more reliably in Python.
- Retrying the same incompatible contract through strict, best-effort, JSON-object, and plain-JSON modes could not fix that mismatch.

### Provider contract and parser

- Replaced the unconstrained question-type field with an explicit JSON-Schema enum containing the ten supported competencies.
- Reduced the provider-facing question object to six content fields only: `stem_en`, `choices`, `proposed_correct_index`, `rationale_en`, `evidence_ru`, and `question_type`.
- Removed provider responsibility for internal ILR and difficulty metadata; the requested session level and provisional difficulty are now assigned deterministically in Python.
- Added normalization for common hosted-model variants, including `items`/`question_set` envelopes, `options` dictionaries, answer letters, alternate field names, and safe question-type synonyms.
- Extra provider metadata is discarded before strict internal validation instead of causing the complete bundle to fail.
- Short-but-structured stems and rationales now reach deterministic quality validation and targeted repair rather than consuming all provider-output modes at the parsing layer.
- Validation failures now report exact field locations and messages without logging the generated passage, choices, keys, or secrets.
- Lowered question-authoring and question-repair temperatures for more stable structured output.
- Bumped the prompt contract to `genai-pipeline-v6` and explicitly documents the exact top-level and per-question shape.

### QA

- Expanded the suite from 88 to 93 tests.
- Added regression tests proving that the provider JSON Schema contains the required question-type enum and excludes internal difficulty/ILR fields.
- Added realistic hosted-payload normalization tests for alternate envelopes, choices dictionaries, answer letters, field aliases, extra metadata, and question-type synonyms.
- Added a first-attempt provider test showing a previously rejected question payload is accepted without exhausting eight output modes.
- Added a full generation-and-persistence integration test showing a normalized hosted question bundle is validated, stored, indexed, and assigned the requested ILR in Python.
- Re-ran the starter-bank validator, Space dependency validator, Gradio smoke test, full automated suite, and HTTP launch check.

## v1.2.6 — Hosted GenAI runtime reliability fix

### Root cause

- Fresh-AI failures were intentionally recoverable, but the UI could make a silent bank fallback look like successful generation.
- Structured-output attempts were provider-major rather than mode-major, so one provider could consume most of a stage budget before the configured fallback provider received a comparable attempt.
- Blind verification made one hosted request per question, multiplying latency, quota consumption, and failure probability for Reading and Listening bundles.
- Deterministic provider tests did not reproduce all hosted-provider schema and entitlement failure modes.

### Provider and prompt pipeline

- Reordered hosted attempts fairly by output strength and provider: both providers receive strict-schema opportunities before weaker modes are attempted.
- Added an optional controlled plain-JSON mode that accepts only one complete JSON document and never extracts arbitrary brace substrings.
- Added batched blind verification for all questions in a passage bundle while continuing to hide proposed keys and independently shuffle verifier choice order.
- Retained an optional second batch only for higher-risk questions.
- Increased verifier output budgets and made stage budgets scale with bundle size.
- Normalized benign audit values such as `none` and `no issues` without weakening substantive rejection gates.

### Diagnostics and UX

- Added sanitized per-stage provider/model/mode/attempt logs controlled by `GENERATION_DIAGNOSTICS` and `LOG_LEVEL`.
- Added explicit accepted-fresh versus bank-fallback banners in the active session.
- Expanded fallback reasons while keeping secrets, full prompts, and generated content out of logs.
- Added useful authentication, permission, quota, rate-limit, model-not-found, and timeout messages.

### QA

- Expanded the suite from 83 to 88 tests.
- Added hosted-provider failover, complete-document JSON fallback, arbitrary-brace rejection, batched-verifier privacy, and redacted permission-error tests.
- Ran a live Gradio client Fresh-AI session against the production orchestration with a deterministic provider: one accepted passage, two accepted questions, four provider calls, zero fallback, immediate bank indexing, and manifest persistence.
- Revalidated the 27-passage/88-question starter bank and all 87 Gradio components.

## v1.2.5 — Reading session multi-select runtime fix

### Root cause

- Fixed a Gradio 6 runtime payload edge case where one selected CheckboxGroup value could arrive as a scalar string.
- The stock CheckboxGroup preprocessor treated the scalar as an iterable and validated it character-by-character, so `Government and politics` failed as `G` and `Culture and society` failed as `C` before the Reading callback could run.
- Confirmed that the repeated `BaseEventLoop.__del__` warnings are unrelated startup/finalizer noise and were not the cause of the failed Reading session.

### Runtime hardening

- Added a scalar-tolerant native CheckboxGroup factory that wraps a single selection into a one-item list before Gradio's standard choice validation.
- Applied the component to both Topics and Comprehension competencies.
- Added independent callback-side normalization, duplicate removal, and allow-list validation so direct API clients and future UI changes cannot reintroduce malformed selection state.
- Invalid selections now fail through the existing recoverable session-start screen instead of raising an uncaught queue preprocessing error.

### QA

- Expanded the automated suite from 78 to 83 tests.
- Added tests for scalar topic selection, scalar competency selection, normal multi-value selection, invalid-value rejection, and recoverable callback behavior.
- Verified a live Gradio API session start using scalar `Government and politics` and `main idea` payloads; the Reading session started and returned a valid passage bundle.

## v1.2.4 — Visible loading feedback and durable generated-bank updates

### User feedback and duplicate-click prevention

- Added a dedicated accessible activity panel with an animated spinner, `aria-live`, and `aria-busy` state.
- Begin Session, Resume, Play Audio, Submit Passage, Show Hints, partial-report generation, and strict-session abandonment now change the initiating button to a busy label and disable it immediately.
- Added staged progress reporting for session creation, content selection, live authoring, adaptive scoring, checkpoint writes, and audio preparation.
- Kept strict one-play behavior intact while making audio preparation visibly acknowledged.

### Generated-bank correctness and durability

- Added `GeneratedBankPersistence` with an atomic local/mounted source of truth and optional Hugging Face Dataset mirroring.
- Every accepted live bundle now refreshes a SHA-256 health manifest containing record, passage, question, audio, and validation-report counts.
- Confirmed accepted passage, question, answer, rationale, evidence, validation, generation, and audio records are committed together before entering the in-memory operational indexes.
- Added immediate dynamic bank counts to setup/session status so users can see the reusable bank grow.
- Added startup merge and post-commit upload for `generated_items.jsonl`, `generated_items.meta.json`, and generated Listening MP3 files when `HF_DATASET_REPO` is configured.
- Added remote audio restoration and runtime path rewriting after restart.
- Added fail-safe generated-overlay loading: malformed overlay records are warned and excluded without disabling the validated starter bank.
- Tightened operational selection so incomplete bundles and missing Listening audio cannot be selected.

### Configuration and QA

- Added Dataset sync variables and automatic `hybrid` selection when `HF_DATASET_REPO` is configured.
- Added `docs/BANK_PERSISTENCE_AND_LOADING.md`.
- Expanded the automated suite from 73 to 78 tests.
- Added tests for activity feedback wiring, atomic manifest creation, immediate reloadability, corrupted-overlay isolation, and Dataset/audio synchronization.

## v1.2.3 — Hugging Face Listening runtime hardening

### Runtime diagnosis

- Identified the repeated `Invalid file descriptor: -1` tracebacks as a known Gradio 6/Hugging Face Spaces event-loop finalizer issue rather than an application scoring or session-state exception.
- Identified `/graphql` and `/api/graphql` 405 responses as traffic from Gradio's experimental Node SSR layer, which this application does not require.
- Identified base64-embedded MP3 callback payloads as an unnecessary proxy and Content-Length risk for Listening playback.

### Listening delivery fix

- Explicitly disabled Gradio SSR with `ssr_mode=False` for the stable client-rendered Space path.
- Replaced base64 MP3 embedding with Gradio's range-capable `/gradio_api/file=` route.
- Restricted `allowed_paths` to the bundled validated-audio directory and controlled runtime TTS cache only.
- Added reactive Gradio HTML audio binding, autoplay-status messaging, browser-autoplay recovery text, strict end-of-play source removal, and no visible native audio controls.
- Replaced per-request asyncio loop creation with one reusable background TTS event loop and bounded TTS timeout handling.
- Preserved checkpoints and bank fallback on all audio errors.

### QA

- Expanded the suite from 68 to 73 tests.
- Added regression coverage for SSR disablement, minimal exposed audio paths, URL-based audio delivery, no base64 payloads, path encoding, and reactive strict-playback binding.
- Verified HTTP 200 app startup, HTTP 200 complete MP3 delivery, HTTP 206 byte-range delivery, and a stateful Listening start/play callback through `gradio_client`.

## v1.2.2 — Hugging Face dependency-resolution hotfix

- Replaced the incompatible `pydantic==2.13.4` pin with `pydantic==2.12.5`, matching the constraint imposed by `gradio[mcp,oauth]==6.5.1` in the Hugging Face Space builder.
- Kept Gradio `6.5.1`, Python `3.11`, the GenAI provider code, prompts, API secret names, item bank, and application behavior unchanged.
- Moved `pytest` out of the production Space dependency set into `requirements-dev.txt`.
- Added `scripts/check_space_dependencies.py` to evaluate repository pins against Gradio base, OAuth, and MCP dependency metadata.
- Added three dependency regression tests covering the Gradio/Pydantic pair and production/dev requirement separation.
- Re-ran the complete test suite, bank validator, Gradio smoke test, and HTTP launch check.

## v1.2.1 — Hugging Face build metadata hotfix

- Quoted `python_version` and `sdk_version` in the README Space YAML metadata.
- Changed the Space runtime to the explicit string `"3.11"`.
- Fixed the YAML coercion that converted unquoted `3.10` into numeric `3.1`, causing Hugging Face to request the nonexistent `docker.io/library/python:3.1` image.
- Added a regression test that parses the README front matter and verifies both version fields remain strings.
- Re-ran the full automated suite, bank validation, and Gradio smoke test.

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
