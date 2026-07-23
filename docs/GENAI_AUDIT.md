# GenAI/API and Prompt Architecture Audit

## Direct answer about the original API configuration

The original repository did **not** contain real Hugging Face or Groq secret values. It referenced environment variables such as `HF_TOKEN` and `GROQ_API_KEY`. No secret value was copied into this release, because API secrets must remain in a local `.env` file or Hugging Face Space secrets rather than source control.

The provider capability was preserved and expanded:

- Hugging Face Inference Providers remain supported.
- Groq remains supported.
- Ordered provider fallback remains supported.
- The original `GENAI_PROVIDER` environment name remains a backward-compatible alias.
- The original `HF_PROVIDER` routing setting is restored.
- New `GENERATION_PROVIDER` and `VERIFICATION_PROVIDER` settings make authoring and verification roles explicit.

## What happened to the original prompt code

The original `core/prompts.py` contained useful Russian assessment-design guidance, but it also contained unsafe or validity-reducing behavior. It was not retained line-for-line.

### Useful behavior preserved and improved

- Reading and Listening have separate genre and discourse guidance.
- Every ILR half-band from 0 through 3 has level-specific authoring guidance.
- Listening prompts require spoken Russian rather than padded written articles.
- Repair and audit stages remain available.
- Topic and competency controls influence authoring.
- Passage length is bounded, but discourse complexity is treated as the primary level signal.
- English orientation, English questions/choices, and Russian source content are enforced.

### Behavior intentionally removed

- Fixed `Q1=A, Q2=B, Q3=C, Q4=D` answer patterns.
- Prompt instructions that tried to make the model randomize answer letters.
- Free-form extraction of the first apparent `{...}` substring.
- Paragraph-count formulas as the main definition of ILR difficulty.
- Trusting the author model's answer key without a blind verification pass.
- Treating the author model's ILR label as calibrated item difficulty.
- One monolithic prompt that generated passage, questions, answers, and audit claims together.

## Findings in the v1.1 hybrid release

The hybrid release correctly restored user-requested live generation and generated-bank persistence, but its GenAI layer still needed substantial work:

1. Passage and question generation were compressed into one short all-in-one schema.
2. Much of the original level-specific Reading/Listening design guidance was lost.
3. Passage naturalness and level fit did not receive a separate independent audit.
4. Author and verifier could silently be the same provider/model.
5. Provider requests used JSON-object mode rather than preferring provider-enforced JSON Schema.
6. Token budgets were not adjusted by stage, level, or bundle size.
7. Raw failed provider attempts were not tracked in session analytics.
8. Structured-output fallback could make too many calls during repeated failures.
9. Quarantine payload redaction depended on callers rather than the persistence boundary itself.
10. The default Groq model setting needed migration away from an announced retirement.
11. The pinned Groq and Edge TTS packages were old.
12. There were no dedicated tests proving key-hiding, staged verification, legacy environment compatibility, schema-first calls, repair behavior, or secret exclusion.

## v1.2 staged generation pipeline

`core/prompts.py` and `core/generation.py` now implement the following sequence:

1. **Passage authoring**
   - Creates only a Russian passage/transcript and passage metadata.
   - Uses skill-, mode-, and ILR-specific guidance.
   - Receives controlled topic/competency guidance and a novelty summary from the current bank.

2. **Deterministic passage gate**
   - Checks Russian-language ratio, hard length limits, sentence repetition, repeated n-grams, markup/TTS hazards, upper-level discourse development, and protected-test references.

3. **Independent passage audit**
   - Uses the verifier role, preferably a different configured provider and/or model.
   - Checks natural Russian, coherence, orientation leakage, translation artifacts, contradictions, repetition, protected-content risk, and provisional level fit.
   - `GENERATION_AUDIT_MODE=smart` saves one call only for lower-risk Reading Training content. Diagnostic, Simulation, Listening, ILR 2+, and ILR 3 remain audited.

4. **Passage repair**
   - Receives only the candidate and explicit failure reasons.
   - Returns a complete typed replacement.
   - Repair attempts are bounded.

5. **Question authoring**
   - Runs separately after passage acceptance.
   - Produces English stems and four English choices.
   - Uses a zero-based proposed answer index, never an answer letter.
   - Requires exact short Russian evidence and English rationale.

6. **Deterministic question gate**
   - Checks unique/near-duplicate choices, evidence support, orientation leakage, choice-length leakage, duplicated evidence, duplicated stems, question-level fit, and bundle constraints.

7. **Blind answer verification**
   - Randomly reorders choices before verification.
   - Does not provide the proposed answer or correct key.
   - Rejects disagreement, multiple defensible answers, outside knowledge, insufficient evidence, reasoning mismatch, answer leakage, or unsupported verifier evidence.

8. **Second verifier for higher-risk items**
   - Optional for ILR 2+/3 inference, intent, tone, relationship-of-ideas, and meaning-in-context items.

9. **Question repair**
   - Uses deterministic and verifier failure reasons.
   - Returns a complete typed replacement set.

10. **Python-side answer positioning**
    - Shuffles choices after all semantic validation.
    - Remaps the key in code.
    - Selects a least-used answer position to maintain long-run bank balance.
    - Applies a separate session-level shuffle for each learner.

11. **Listening audio gate**
    - Generates content-hashed cached TTS.
    - Verifies existence, non-empty size, and reasonable duration.

12. **Atomic persistence or quarantine**
    - Accepted records are written to the generated-bank overlay and indexed immediately.
    - Failed records are quarantined with stage trace, failure reasons, provider metadata, request count, repair count, and token usage when supplied.
    - Secret-bearing text is recursively redacted at the quarantine persistence boundary.

## Structured output and provider routing

The hosted provider path attempts:

1. strict JSON Schema;
2. best-effort JSON Schema;
3. JSON-object fallback only when needed.

Every response is still validated with strict Pydantic models. A response cannot enter the bank merely because it is valid JSON.

Author and verifier routing are independent:

- `GENERATION_PROVIDER` controls authoring order.
- `VERIFICATION_PROVIDER=auto` reverses that order where possible.
- Separate author and verifier model variables are provided for both Hugging Face and Groq.
- Startup warnings identify same-provider/same-model verification, disabled audits, weaker JSON-object-only mode, and known deprecated model settings.

## Cost and quota controls

- Per-session fresh-bundle limit.
- Global generation concurrency limit.
- Provider timeout and bounded exponential retry.
- Maximum outbound attempts per structured-output stage.
- Stage/level/bundle-aware token budgets beneath administrator-configured hard caps.
- Optional smart passage-audit policy.
- Secondary verification restricted to higher-risk item types and bands.
- Successful and failed provider calls are counted.
- Generated metadata stores author/verifier provider, model, prompt/pipeline version, calls, repairs, and token usage when the provider reports it.
- Any failure preserves the session and selects an accepted bank item.

## Environment compatibility

Original names retained:

```text
HF_TOKEN
GROQ_API_KEY
GENAI_PROVIDER
HF_PROVIDER
HF_TEXT_MODEL
GROQ_MODEL
```

Preferred/current names added:

```text
GENERATION_PROVIDER
VERIFICATION_PROVIDER
HF_VERIFIER_MODEL
GROQ_VERIFIER_MODEL
STRUCTURED_OUTPUT_MODE
GENERATION_AUDIT_MODE
GENERATION_REPAIR_ATTEMPTS
SECOND_VERIFIER_HIGH_RISK
MAX_PROVIDER_ATTEMPTS_PER_STAGE
PASSAGE_MAX_TOKENS
QUESTION_MAX_TOKENS
REPAIR_MAX_TOKENS
AUDIT_MAX_TOKENS
VERIFIER_MAX_TOKENS
```

`GENERATION_PROVIDER` takes precedence when both it and legacy `GENAI_PROVIDER` are set.

## Remaining GenAI limitations

- Model verification reduces risk but is not equivalent to expert human item review or empirical calibration.
- When only one provider/model is configured, validator independence is necessarily weaker; the app warns about same-model configurations.
- Provider token-usage fields vary. Call counts are always tracked, but token totals are recorded only when returned by the provider SDK.
- Live generation has not been tested against real user API keys in this build environment; deterministic provider tests exercise the same schemas, repair, validation, persistence, and fallback code.
- Authentic/open-licensed source ingestion remains an administrator workflow. Public live generation creates synthetic material only.
