# Architecture

## Operational modules

`app.py` remains thin. `ui/layout.py` builds the Gradio interface and `ui/callbacks.py` coordinates mode-appropriate interaction while delegating:

- session state and strict flow to `core/session.py`;
- Bayesian updates and item information to `core/adaptive.py`;
- starter/generated bank indexing and atomic writes to `core/item_bank.py`;
- generated-bank manifests, mounted persistence, and optional HF Dataset synchronization to `core/bank_persistence.py`;
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

The bank loads once at startup, maintains passage/question/audio indexes in memory, rejects duplicate IDs/content, and immediately indexes newly accepted generated bundles. Operational passage validation and health summaries are cached and invalidated whenever the bank is reindexed. `generated_items.meta.json` records the overlay checksum and record counts after every commit. Incomplete bundles, invalid questions, malformed overlay records, and Listening items without either a local file or a durably indexed remote MP3 are never selectable.

When `HF_DATASET_REPO` is configured, `GeneratedBankPersistence` merges the remote overlay before indexing. Remote MP3s are registered but not downloaded in bulk; the selected file is restored lazily and prefetched in the background. After an accepted local atomic commit, the persistence layer mirrors the JSONL snapshot, health manifest, and new Listening MP3s. Remote sync failure cannot roll back the already accepted local/in-memory bundle.


## Performance and audio-cache path

- Bank-only Reading/Listening selection reuses cached operational indexes instead of rerunning deterministic validation for every request.
- The selected remote Listening MP3 is prefetched while the learner reads; all other remote audio remains untouched.
- Selected Training/strict neural upgrades are also warmed in the background. A per-output cache lock ensures prefetch and an immediate Play click wait on the same render.
- Independent Edge dialogue turns use at most three concurrent synthesis requests. Piper synthesis remains serialized because the free CPU tier has limited RAM and local model objects are not assumed thread-safe.
- Newly generated Listening uses an explicit Training voice/speed for the first canonical render when one was selected, allowing playback to reuse that file.
- Temporary MP3 names include thread/time identifiers so concurrent renders cannot overwrite each other's partial files.

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

The session requests a new bundle before bank selection. The requested level is the active skill's bounded routing band. Training target level remains a selection bias inside the configured floor/ceiling rather than overriding demonstrated performance.

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
- reports low confidence.

The verifier's own `evidence_quote_ru` is advisory rather than a duplicate hard
gate. Its exactness and traceability are recorded in validator scores. The
operational `QuestionItem.evidence_ru` remains subject to the hard exact-source
check before verification and again before persistence.

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

### 10. Atomic persistence, indexing, and optional remote mirror

Accepted passage, questions, validation reports, and audio metadata are committed together through atomic file replacement. Only after the file commit succeeds are the objects inserted into the live indexes. A health manifest is refreshed with checksum and counts.

Mounted storage uses the same path abstraction. The optional HF Dataset backend uploads the JSONL, manifest, and generated audio after every accepted bundle and restores/rewrites remote audio paths at startup. Failed candidates are quarantined with a stage trace and recursively redacted error data.

## Visible operation-state UX

Slow actions use a two-step Gradio event chain. A non-queued pre-event immediately displays an accessible animated activity panel and disables/renames the initiating button. The queued assessment callback then performs the work and emits staged `gr.Progress` descriptions. A final event clears the activity panel while preserving mode-specific button interactivity, including strict one-play Listening.

This pattern is applied to session start/recovery, audio preparation, passage submission, hints, report generation, and strict-session abandonment. It supplements—not replaces—idempotent nonce handling and server-side session rules.

## Hosted provider layer

Supported routes:

- Hugging Face only;
- Groq only;
- Hugging Face then Groq;
- Groq then Hugging Face;
- deterministic mock for tests/admin development only;
- disabled bank-only mode.

For each structured stage, the provider attempts modes in provider-fair order:

1. strict JSON Schema across configured providers;
2. best-effort JSON Schema across configured providers;
3. JSON-object mode across configured providers;
4. optional controlled whole-document JSON across configured providers.

The plain-JSON path accepts only one complete JSON document and never scrapes an arbitrary first brace substring. A per-stage outbound attempt cap prevents runaway retries. Timeouts, bounded exponential backoff, provider fallback, global generation concurrency, and per-session bundle limits protect quotas.

Blind answer verification is performed as one indexed batch per passage bundle. Python independently reorders each question's choices before the request and never sends the proposed key. Optional second verification is another batch containing only high-risk items.

Stage/level/bundle-aware token budgets are bounded by administrator-configured caps. Provider-reported prompt/completion tokens are stored when available. Outbound calls are counted even when a request fails.

## Ability model

Each skill maintains a separate posterior over a fixed theta grid. Diagnostic/Simulation use a broad medium prior; Training centers the prior on the selected starting band.

Item likelihood uses a provisional chance-aware form for four-choice items:

```text
P(correct) = c + (1 - c) / (1 + exp(-a(theta - b)))
```

with initial `a=1.0` and `c=0.25`. Questions from the same passage are testlet-dependent, so their likelihood contribution is discounted by `1/sqrt(k)` for a `k`-question passage. Posterior mean is the EAP estimate; posterior standard deviation and interval represent uncertainty.

Generated difficulty is never accepted as calibrated truth. Initial `b` blends the requested band and documented question-type reasoning offset within bounded limits.

## Adaptive delivery routing

The continuous posterior and the passage-delivery band are separate. `AbilityEstimate.routing_ilr` begins at ILR 2 for neutral Diagnostic/Simulation starts or at the selected starting band for Training and targeted-start Diagnostics.

After each passage, `update_routing_band()` calculates posterior mass across the adjacent ILR boundary midpoints. A 56% directional posterior probability plus at least two scored questions moves the delivery band one adjacent half-level; otherwise it holds. A passage can never cause a multi-level jump, and the route is clamped to `SessionState.minimum_ilr` and `maximum_ilr`.

`select_passage()` first enforces the allowed ILR range using calibrated difficulty when available and provisional authoring level otherwise. It prefers the current routing band, falls back only to the nearest eligible band, then ranks candidates using normalized information, ability distance, content balance, exposure control, Training target bias, and calibration status. A deterministic top-candidate randomization reduces systematic overexposure.

Adaptive Diagnostic selection may temporarily probe an under-sampled adjacent band without changing the current routing band. Confidence-based stopping requires minimum length, standard error at or below 0.45, and evidence in the current band plus at least one adjacent band. See `docs/ADAPTIVE_ROUTING.md`.

## Estimate conversion and reporting

The continuous estimate is converted to the nearest provisional ILR anchor only after minimum evidence. Uncertainty, adjacent-band evidence, and question count constrain whether a working band is reported and whether it is considered stable.

The report always distinguishes provisional practice guidance from official DLPT scoring and can return “Insufficient evidence for a stable provisional working band.”
