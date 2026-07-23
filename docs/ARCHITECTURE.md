# Architecture

## Operational modules

`app.py` remains thin. `ui/layout.py` builds the Gradio interface and `ui/callbacks.py` coordinates mode-appropriate interaction while delegating:

- session state and strict flow to `core/session.py`;
- Bayesian updates and item information to `core/adaptive.py`;
- starter/generated bank indexing and atomic writes to `core/item_bank.py`;
- staged hosted authoring to `core/generation.py`;
- level- and skill-specific prompt construction to `core/prompts.py`;
- deterministic bank gates to `core/validation.py`;
- audio lifecycle to `core/audio.py`;
- checkpoint/history/export persistence to `core/storage.py`;
- score conversion to `core/scoring.py`;
- learner reporting to `core/reporting.py`.

## Hybrid operational bank

The selectable bank is the union of:

```text
data/starter_items.jsonl
storage/item_bank/generated_items.jsonl
```

The first is immutable release content. The second is an atomic writable overlay. With mounted Space storage, the overlay resolves to `/data/item_bank/generated_items.jsonl`.

The bank loads once at startup, maintains passage/question/audio indexes in memory, rejects duplicate IDs/content, and immediately indexes newly accepted generated bundles.

## Content selection paths

### Bank-only

The adaptive selector chooses among all accepted active starter and generated passages. It applies:

- active-skill ability and uncertainty;
- item information and difficulty distance;
- Training target-level bias;
- topic, genre, and question-type balance;
- item/passage exposure;
- current-session and optional profile-history no-repeat controls;
- provisional versus future calibrated metadata.

### Fresh-AI preferred

The session requests a new bundle before bank selection. The requested level is derived from the active skill posterior; Training blends the current estimate with the selected target band.

A failed fresh request does not mutate completed responses. The callback records failed provider calls/repairs, pauses timer accounting for loading time, and selects a bank item.

## Staged GenAI pipeline

### 1. Passage authoring

`core/prompts.py` creates a constrained prompt using skill, mode, provisional target band, topics, competencies, bank novelty context, and a nonce. Live user authoring is always labeled synthetic.

The author provider returns `CandidatePassageDraft` only. It cannot simultaneously invent questions and certify its own answer keys.

### 2. Deterministic passage gate

Checks include:

- predominantly Russian content;
- hard Reading and Listening length proxies;
- repeated sentences and long n-grams;
- long/TTS-hostile sentences;
- markup artifacts;
- protected-test/affiliation references;
- upper-level discourse development;
- target-level and metadata consistency.

### 3. Independent passage audit

A verifier role checks natural Russian, coherence, orientation safety, provisional level match, repetition, contradictions, translation artifacts, and protected-content risk.

`VERIFICATION_PROVIDER=auto` reverses the author provider order where possible. Separate verifier model settings exist for both hosted providers.

Audit policy:

- `always`: audit every passage;
- `smart`: audit all Diagnostic/Simulation, all Listening, and ILR 2+/3 content; skip only lower-risk Reading Training passage audit;
- `off`: deterministic passage checks remain, but startup warns that the audit is disabled.

### 4. Repair

Passage and question repairs are separate bounded calls. Each repair receives the defective typed candidate and explicit failure reasons, then must return a complete replacement object.

### 5. Question authoring

After passage acceptance, a separate call returns `CandidateQuestionSet` with English stems/choices, zero-based proposed indices, English rationales, exact short Russian evidence, question types, and provisional difficulty metadata.

### 6. Deterministic question gate

Checks include:

- exact bundle count and skill limits;
- four unique and non-near-duplicate choices;
- English-language dominance with allowance for quoted Russian terms;
- exact evidence support and evidence size;
- passage/question linkage and status;
- duplicate stems/evidence;
- answer-position/length/absolute-word leakage;
- orientation answer leakage;
- level-inappropriate question types;
- ILR 3 overuse of isolated detail.

### 7. Blind verification

Before verification, Python randomizes choice order. The verifier receives the Russian source, English stem, reordered choices, target band, and question type—but never the proposed key.

The item is rejected when the verifier:

- selects another answer;
- finds multiple defensible choices;
- requires outside knowledge;
- finds insufficient evidence;
- finds reasoning-level mismatch;
- detects answer leakage;
- supplies evidence not present in the source;
- reports low confidence.

Higher-risk ILR 2+/3 items may receive a second verifier pass.

### 8. Answer-position handling

Semantic validation occurs before answer positioning. Python then:

1. selects a currently least-used bank answer position;
2. shuffles all choices;
3. remaps the key;
4. records the shuffle map;
5. revalidates the item;
6. later applies a separate learner/session shuffle.

No prompt prescribes an A/B/C/D sequence.

### 9. Listening audio

Accepted Listening transcripts are content-hash cached by transcript, voice, rate, and engine version. Audio must exist, be non-empty, and have plausible duration before the bundle is persisted.

### 10. Atomic persistence or quarantine

Accepted passage, questions, validation reports, and audio metadata are appended atomically to the generated overlay. Failed candidates are quarantined with a stage trace and recursively redacted error data.

## Hosted provider layer

Supported routes:

- Hugging Face only;
- Groq only;
- Hugging Face then Groq;
- Groq then Hugging Face;
- deterministic mock for tests/admin development only;
- disabled bank-only mode.

For each structured stage, the provider attempts:

1. strict JSON Schema;
2. best-effort JSON Schema;
3. JSON-object fallback.

A per-stage outbound attempt cap prevents runaway retries. Timeouts, bounded exponential backoff, provider fallback, global generation concurrency, and per-session bundle limits protect quotas.

Stage/level/bundle-aware token budgets are bounded by administrator-configured caps. Provider-reported prompt/completion tokens are stored when available. Outbound calls are counted even when a request fails.

## Ability model

Each skill maintains a separate posterior over a fixed theta grid. Diagnostic/Simulation use a broad medium prior; Training centers the prior on the selected starting band.

Item likelihood uses the provisional Rasch/1PL form:

```text
P(correct) = 1 / (1 + exp(-a(theta - b)))
```

with initial `a=1.0`. Posterior mean is the EAP estimate; posterior standard deviation and interval represent uncertainty.

Generated difficulty is never accepted as calibrated truth. Initial `b` blends the requested band and documented question-type reasoning offset within bounded limits.

## Estimate conversion and reporting

The continuous estimate is converted only after minimum evidence. Predicted success across ILR reference difficulties, uncertainty, adjacent-band evidence, and question count constrain the reported practice band.

The report always distinguishes provisional practice guidance from official DLPT scoring and can return “Insufficient evidence for a stable estimate.”
