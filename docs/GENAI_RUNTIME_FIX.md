# GenAI Runtime Fix — v1.2.6

## What actually failed

The repeated `BaseEventLoop.__del__` / `Invalid file descriptor: -1` messages appear during Gradio startup and do not identify whether a Reading or Listening generation succeeded. The operational defect was later in the Fresh-AI path: hosted generation failures were recoverable, so the session silently selected an existing bank passage. That protected the learner's session but made it look as though the generation button did nothing.

The previous hosted pipeline had been exercised end to end with deterministic providers but had three production weaknesses:

1. It could spend most of a stage's bounded attempts on one provider's strict, best-effort, and JSON-object variants before trying the fallback provider.
2. It sent one blind-verification request per question, and higher-risk questions could trigger a second request each. A Reading bundle could therefore require many sequential hosted calls after passage and question authoring.
3. It exposed the fallback note only as ordinary session text and emitted too little safe diagnostic information in the Space container log.

## Runtime corrections

### Fair provider and output-mode routing

The provider plan is now ordered by output strength and then provider. With Hugging Face and Groq configured, both receive a strict-schema attempt before either consumes weaker modes. The bounded stage limit still protects quota and latency.

The ordered modes are:

1. strict JSON Schema;
2. best-effort JSON Schema;
3. JSON object;
4. optional controlled plain JSON.

Controlled plain JSON accepts only one complete JSON document, optionally enclosed in one Markdown JSON fence. It does not scrape the first brace-delimited substring out of arbitrary model prose. All modes still undergo strict Pydantic validation.

### Batched blind verification

All questions in a passage bundle are independently shuffled and sent in one verification request. Proposed answers are not included. The verifier returns one indexed decision for every question. Python maps the verifier's selected index back to the candidate choice and rejects missing, duplicate, ambiguous, unsupported, or disagreeing results.

High-risk items may receive one additional batch from the configured secondary verifier. The pipeline no longer makes a separate primary request for every question.

### More tolerant audit parsing

Audit arrays containing benign model text such as `none`, `no issues`, or `not detected` are normalized as empty. Real contradiction, repetition, translation-artifact, or leakage descriptions remain rejection signals.

### Visible status and safe diagnostics

The session banner now explicitly says either:

- `Fresh AI bundle generated, validated, saved, and selected`; or
- `Fresh AI fallback`, with a sanitized reason and the selected bank fallback.

When diagnostics are enabled, logs include stage, provider, model, output mode, and attempt number. They do not include tokens, secrets, full prompts, or generated passage text. Typical messages are:

```text
GenAI request purpose=author schema=CandidatePassageDraft provider=hf ...
GenAI attempt failed ...
Fresh bundle accepted ...
Fresh generation failed; using bank fallback ...
```

### Persistence remains fail-closed

A generated bundle is selectable only after:

1. typed passage and question validation;
2. independent passage audit when required;
3. deterministic item checks;
4. blind answer verification;
5. code-side answer shuffle and key remapping;
6. duplicate detection;
7. Listening TTS creation and validation when applicable;
8. atomic bank commit and manifest refresh.

The accepted objects are inserted into the in-memory index immediately. If persistence or validation fails, the item is quarantined and the session uses an already accepted bank item without losing completed responses.

## Configuration additions and defaults

```text
MAX_PROVIDER_ATTEMPTS_PER_STAGE=8
ALLOW_PLAIN_JSON_FALLBACK=true
GENERATION_DIAGNOSTICS=true
VERIFIER_MAX_TOKENS=2400
LOG_LEVEL=INFO
```

The existing names remain supported:

```text
HF_TOKEN
GROQ_API_KEY
GENERATION_PROVIDER
GENAI_PROVIDER
HF_PROVIDER
HF_TEXT_MODEL
GROQ_MODEL
```

## Verification performed

- 88 automated tests passed.
- Added provider-order, controlled-JSON, malformed-prose, batch-verifier privacy, and permission-error regression tests.
- Starter/combined bank validator passed with 27 passages, 88 questions, and 15 audio assets.
- Gradio layout smoke test passed with 87 components.
- A live local Gradio client selected `Fresh AI preferred`, invoked the real session callback, generated a deterministic fresh Reading bundle through the production orchestration layer, validated it, committed it, indexed it, and selected it.
- The integration session reported one fresh generation, zero bank fallbacks, four provider calls, and one generated passage/two generated questions in the bank manifest.

No real hosted Hugging Face or Groq key was available in the release environment. Therefore, provider authentication, account entitlement, live model availability, latency, and quota must still be confirmed in the deployed Space. The production adapter itself is covered with realistic simulated strict-mode failures, cross-provider success, controlled plain-JSON fallback, and sanitized error handling.
