# Test Results

Executed in the v1.2.1 Hugging Face metadata-hotfix environment on 2026-07-23.

## Automated unit/integration suite

```text
65 passed
```

Core coverage includes:

- independent Reading and Listening estimates;
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

- no fixed `Q1=A, Q2=B, Q3=C, Q4=D` or equivalent prompt sequence;
- zero-based answer indices rather than answer letters;
- blind verifier receives no proposed key;
- author, passage-audit, question, and blind-verification stages are separate;
- strict JSON Schema is attempted before weaker output modes;
- original `GENAI_PROVIDER` and `HF_PROVIDER` environment compatibility;
- generated provider/model/pipeline/call/repair metadata persistence;
- deterministic passage repair and repair-count persistence;
- meaningful smart-audit behavior;
- provider stage-attempt cap;
- successful and failed provider-call accounting;
- generated-bank atomic append and reload;
- duplicate generated-content quarantine;
- recursive secret redaction in quarantine;
- API secret exclusion from Settings serialization;
- unavailable-provider and generation-limit fallback;
- generated Listening audio validation and caching.

## Hugging Face metadata regression

The README front matter is parsed during testing. The release requires:

```yaml
sdk: gradio
sdk_version: "6.5.1"
python_version: "3.11"
app_file: app.py
```

Both version fields are asserted to be YAML strings. This prevents `3.10` from being coerced to numeric `3.1` and sent to the container builder as `python:3.1`.

## Combined bank validation

```text
Passages: 27
Questions: 88
Audio assets: 15
Answer positions: {'A': 22, 'B': 22, 'C': 22, 'D': 22}
VALIDATION PASSED
```

The validation command loads both the immutable starter path and writable generated overlay. The packaged overlay is empty by design.


## Full-length simulation flow

Deterministic bank-only Simulation flows completed independently for both skills:

```text
Reading:   35 questions across 9 passage bundles
Listening: 35 questions across 13 passage bundles
```

Both runs used strict mode state, no repeated passage, all-questions-required submission, and independent ability updates.

## Gradio Space smoke test

```text
Smoke test passed: 27 passages, 88 questions, 84 UI components.
Live generation ready=False: no matching API key; Fresh AI falls back to bank.
```

This is the expected no-secret release state.

## Deterministic staged-generation integration

The test-only mock provider exercised:

1. passage generation;
2. deterministic passage checks;
3. independent passage audit;
4. separate question generation;
5. blind verification for each question;
6. Python answer-position balancing and key remapping;
7. deterministic post-shuffle validation;
8. atomic generated-bank append;
9. reload into a new `ItemBank` instance;
10. duplicate rejection and quarantine.

A deliberately defective passage was repaired and persisted with `repair_count=1`. A failing provider attached raw call counts to the raised error while quarantine removed the supplied secret string.


## Real local launch check

`python app.py` started the v1.2 interface on `127.0.0.1:7860`. An HTTP request returned:

```text
HTTP status: 200
Rendered HTML: 113,413 bytes
```

## Pinned release dependencies

```text
Gradio 6.5.1
Pydantic 2.13.4
huggingface-hub 1.16.1
python-dotenv 1.2.2
edge-tts 7.2.8
groq 1.5.0
pytest 9.0.2
```

The current environment contained the Gradio/Pydantic/Hugging Face/pytest runtime used for tests. Hosted Groq and Edge TTS imports are lazy, so bank-only startup and deterministic tests do not require those packages to be imported until their features are used.

## External-provider test limitation

No real user API keys were available in the execution environment, so the release did not spend tokens or make live hosted-generation calls. The deterministic providers exercise the same prompt builders, schemas, staged pipeline, repair logic, blind verification, persistence, audio integration, and fallback code. Real-provider availability and model entitlement must still be verified in the deployed Space account.
