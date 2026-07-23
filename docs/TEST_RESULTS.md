# Test Results

Executed for the v1.2.4 loading-feedback and generated-bank persistence release on 2026-07-23.

## Automated unit/integration suite

```text
78 passed
```

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

Version 1.2.4 adds direct regression coverage for:

- accessible activity spinner and immediate busy-button locking;
- chained Begin Session, Play Audio, and Submit Passage feedback events;
- atomic generated-bank commit;
- generated-bank SHA-256 health manifest;
- immediate in-memory indexing and reload into a new `ItemBank` instance;
- malformed generated-overlay isolation without starter-bank failure;
- Hugging Face Dataset JSONL/manifest/audio upload behavior;
- remote Listening audio restoration and runtime-path rewriting.

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

The packaged generated overlay is empty by design. Runtime-generated accepted bundles are written to the overlay and manifest.

## Full simulation flow

Deterministic bank-only strict simulations completed independently:

```text
Reading:   35 questions across 9 passage bundles; 9 unique passages
Listening: 35 questions across 13 passage bundles; 13 unique passages
```

## Gradio Space smoke test

```text
Smoke test passed: 27 passages, 88 questions, 87 UI components.
Live generation ready=False: no matching API key; Fresh AI falls back to bank.
```

The no-secret result is expected for the release package.

## Local server and audio route

The v1.2.4 app launched with `ssr_mode=False` and returned:

```text
Application page: HTTP 200, 130,025 bytes
Starter MP3: HTTP 200, 29,073 bytes
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

## External-provider limitation

No real user provider keys were available in the execution environment. No hosted tokens were spent. Deterministic providers exercised the same prompt builders, Pydantic schemas, staged audit/repair, blind verification, persistence, audio linkage, and fallback code. Actual model entitlements, provider latency, quotas, and remote Dataset permissions must be verified in the deployed Space account.
