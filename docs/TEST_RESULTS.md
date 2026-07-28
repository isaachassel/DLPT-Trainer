# Test Results

Executed for the v1.3.4 skill-separated bank and audio-integrity release on 2026-07-28.

## Automated unit/integration suite

```text
130 passed
```



Version 1.3.4 additionally verifies:

- Reading and Listening maintain disjoint passage/question indexes.
- Skill-specific topic lists update correctly for Reading, Listening, and combined sessions.
- Reading bundles carrying audio metadata or assets are rejected.
- Listening bundles without validated, transcript-linked, non-empty audio are rejected.
- Same-skill duplicates are rejected while cross-skill equivalents are stored as related content.
- Cross-skill repeat exposure is suppressed by content hashes during selection.
- Bank-health totals and operational audio counts reconcile by skill.

Version 1.3.3 additionally verifies:

- a Listening candidate with one near-duplicate distractor pair repairs only the failed question rather than discarding the passage and all valid questions;
- valid parallel answer frames such as “open” versus “close” are not falsely rejected solely because their grammar is parallel;
- tiny qualifier-only differences remain rejected as near duplicates;
- repaired Listening content proceeds through MP3 creation, audio validation, atomic bank persistence, and immediate in-memory reuse;
- the app distinguishes question-validation failure before audio creation from a genuine TTS or audio-validation failure.

Version 1.3.2 additionally verifies:

- a legitimate `B` answer is accepted even when Gradio server-side dynamic-choice metadata is stale or empty;
- answer values outside A/B/C/D are rejected safely;
- hidden question slots no longer clear the stable answer-key contract;
- a live Gradio client can start Reading, submit B responses, advance to the next passage, and produce no `choices: []` traceback;
- configured Dataset repositories are created/access-checked before restore;
- a failed `HF_BANK_TOKEN` falls back to a different working `HF_TOKEN`;
- Dataset synchronization errors are token-redacted and visible in status/log diagnostics;
- explicit manual synchronization can verify and push the current generated bank.

Core coverage includes:

- independent Reading and Listening Bayesian estimates;
- posterior uncertainty reduction;
- Training target-level influence;
- information, content-balance, and exposure scoring;
- answer shuffling and correct-key remapping;
- starter answer-position balance;
- session/history no-repeat controls;
- all-questions-required and strict locked progression;
- idempotent duplicate submission;
- answer-change tracking;
- strict versus Training playback;
- strict/standard timers;
- full 35-question minimum and shortened labels;
- variable Reading/Listening bundle constraints;
- checkpoint restore and safe corruption failure;
- JSON/CSV export;
- audio cleanup and asset validation;
- evidence-aware reporting;
- provider-key errors and bank fallback;
- application import and Gradio configuration generation.

GenAI-specific coverage includes:

- no fixed Q1=A, Q2=B, Q3=C, Q4=D prompt sequence;
- zero-based proposed-answer indices rather than answer letters;
- blind verifier receives no proposed key;
- author, passage-audit, question, and blind-verification stages are separate;
- strict JSON Schema is attempted before weaker output modes;
- original `GENAI_PROVIDER` and `HF_PROVIDER` environment compatibility;
- generated provider/model/pipeline/call/repair metadata persistence;
- deterministic passage repair and repair-count persistence;
- meaningful smart-audit behavior;
- provider stage-attempt cap;
- successful and failed provider-call accounting;
- duplicate generated-content quarantine;
- recursive secret redaction in quarantine;
- API secret exclusion from Settings serialization;
- unavailable-provider and generation-limit fallback;
- generated Listening audio validation and caching.
- fair provider failover before weaker structured-output modes;
- controlled one-document plain-JSON fallback;
- rejection of JSON-looking brace fragments embedded in prose;
- batched blind verification with proposed keys omitted;
- useful and secret-redacted hosted-provider permission errors;
- explicit provider JSON-Schema enums for every supported question type;
- removal of internal target-level and difficulty fields from the provider-facing question contract;
- normalization of alternate question envelopes and field names;
- normalization of A/B/C/D choice dictionaries and proposed answer letters;
- safe normalization of common question-type synonyms;
- exact field-location diagnostics for rejected hosted payloads;
- first-attempt acceptance of a realistic previously incompatible hosted question response;
- full normalized hosted-question generation, validation, persistence, and immediate bank indexing;

Version 1.2.7 retains all prior regression coverage and additionally verifies:

- accessible activity spinner and immediate busy-button locking;
- chained Begin Session, Play Audio, and Submit Passage feedback events;
- atomic generated-bank commit;
- generated-bank SHA-256 health manifest;
- immediate in-memory indexing and reload into a new `ItemBank` instance;
- malformed generated-overlay isolation without starter-bank failure;
- Hugging Face Dataset JSONL/manifest/audio upload behavior;
- remote Listening audio restoration and runtime-path rewriting;
- scalar single-topic CheckboxGroup payload normalization;
- scalar single-competency CheckboxGroup payload normalization;
- normal multi-value CheckboxGroup preservation;
- invalid multi-select allow-list rejection;
- recoverable session-start behavior for malformed direct API selections.

Version 1.2.8 additionally verifies:

- paraphrased blind-verifier evidence is recorded as advisory rather than rejecting an otherwise supported item;
- batched verification preserves accepted status when the verifier quote is non-exact;
- a full generated Reading bundle with paraphrased verifier evidence is accepted, atomically stored, and indexed without repair;
- operational `QuestionItem.evidence_ru` still fails closed when it is not an exact passage substring;
- verifier evidence exactness and traceability scores are persisted in validation reports.

Version 1.2.9 additionally verifies:

- Training passage feedback reveals the passage authoring target and each completed question's intended ILR band;
- every completed question appears in the final question-level ILR review, including correctly answered items;
- provisional item labels explicitly state that the level is provisional;
- empirically calibrated item difficulty is mapped to the nearest displayed half-band while preserving a differing original authoring target;
- active Diagnostic passage presentation does not reveal the passage or question level before submission/completion.

Version 1.3.0 additionally verifies:

- automatic private Dataset repository derivation from the running Space identity;
- automatic private Dataset initialization when no remote bank file exists;
- separate `HF_BANK_TOKEN` use with `HF_TOKEN` fallback;
- legacy `STORAGE_BACKEND=local` upgrade to hybrid persistence on Spaces when auto-provisioning is enabled;
- generated-bank JSONL and manifest upload during automatic provisioning;
- portable generated-bank ZIP export;
- backup import/merge and immediate generated-overlay reload;
- generated Listening audio inclusion and restoration through backup and Dataset paths;
- controlled serving of only audio and generated-bank export directories.

Version 1.3.1 additionally verifies:

- sustained incorrect ILR 3 evidence routes the next passage to ILR 2+, then to ILR 2 after continued weak evidence;
- one isolated incorrect ILR 3 response does not cause a large route jump;
- routing never moves more than one adjacent half-level after a passage;
- routing respects configured minimum and maximum ILR bands;
- neutral Adaptive Diagnostic starts at medium difficulty while selected-band challenge starts remain available;
- bank selection prefers the current routing band and honors a hard ILR 2–3 range;
- Reading and Listening routing histories remain independent;
- final reports include the complete adaptive routing path and movement reasons;
- confidence-based Diagnostic stopping requires current-band and adjacent-band evidence;
- Diagnostic boundary probing targets an under-sampled adjacent band;
- mode controls hide the unused target band outside Training and hide start/target controls in Full Simulation.

## Hugging Face metadata and dependency validation

README front matter:

```yaml
sdk: gradio
sdk_version: "6.5.1"
python_version: "3.11"
app_file: app.py
```

Dependency check:

```text
SPACE DEPENDENCY VALIDATION PASSED
- Gradio: 6.5.1
- Pydantic: 2.12.5 (compatible with gradio[mcp,oauth])
- Hugging Face Hub: 1.16.1
```

## Combined bank validation

```text
Passages: 27
Questions: 88
Audio assets: 15
Answer positions: {'A': 22, 'B': 22, 'C': 22, 'D': 22}
VALIDATION PASSED
```

The release archive intentionally omits blank generated-overlay runtime files. The app creates them only when absent, then mirrors accepted bundles to the configured private Dataset or mounted storage. Portable backup ZIP export/import is also available in the UI.

## Full simulation flow

Deterministic bank-only strict simulations completed independently:

```text
Reading:   35 questions across 9 passage bundles; 9 unique passages
Listening: 35 questions across 13 passage bundles; 13 unique passages
```

## Gradio Space smoke test

```text
Smoke test passed: 27 passages, 88 questions, 101 UI components.
Live generation ready=False: no matching API key; Fresh AI falls back to bank.
```

The no-secret result is expected for the release package.

## Local server and audio route

The v1.2.6 app launched with `ssr_mode=False` and returned:

```text
Application page: HTTP 200, 135,966 bytes
Starter MP3: HTTP 200, 273,906 bytes
Starter MP3 byte range: HTTP 206, 100 bytes returned
Activity-spinner CSS present in rendered application: yes
```

## Generated-bank persistence integration

The deterministic provider exercised the complete accepted-item path:

1. passage authoring;
2. passage validation/audit;
3. question authoring;
4. blind verification;
5. Python choice shuffling and key remapping;
6. post-shuffle deterministic validation;
7. atomic JSONL replacement;
8. health-manifest update;
9. immediate in-memory indexing;
10. reload into a new bank instance;
11. optional Dataset JSONL, manifest, and Listening audio upload.

The manifest test verified one generated Reading passage produced:

```text
1 passage
2 questions
3 validation reports
6 total JSONL records
64-character SHA-256 checksum
```

A simulated remote startup restored a generated MP3 into the current runtime audio cache and rewrote the stored asset path.

## Reading scalar-selection runtime integration

A live Gradio client invoked `/start_session_callback` using scalar payloads rather than arrays:

```text
Topic: Government and politics
Competency: main idea
Result: Reading session started successfully and returned a validated passage bundle
```

This directly reproduces the payload shape that previously caused Gradio to split the selected topic into individual characters.

## Fresh-AI live callback integration

A local Gradio server was started with the production session callback and deterministic hosted-provider substitute. A stateful client selected **Fresh AI preferred** and started a Reading session. The result was:

```text
Fresh generated bundles this session: 1
Bank fallbacks this session: 0
Generated-bank passages: 1
Generated-bank questions: 2
Provider calls: 4
Repairs: 0
```

The status banner reported that the fresh bundle was generated, validated, saved, and selected. The accepted bundle was present in the JSONL overlay, in-memory bank index, and SHA-256 bank manifest.

The hosted adapter was also tested under simulated Hugging Face structured-output failure followed by Groq strict-schema success. The call order was Hugging Face strict schema, then Groq strict schema; it did not spend the entire stage budget on one provider first.

## External-provider limitation

No real user provider keys were available in the execution environment. No hosted tokens were spent. Deterministic providers exercised the same prompt builders, Pydantic schemas, staged audit/repair, blind verification, persistence, audio linkage, and fallback code. Actual model entitlements, provider latency, quotas, and remote Dataset permissions must be verified in the deployed Space account.
