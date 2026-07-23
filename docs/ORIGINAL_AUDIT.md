# Concise Audit of the Original Build

## Original architecture

The submitted repository contained a 386-line monolithic `app.py`, a 1,385-line generation module, a 767-line prompt file, dataclass schemas, and threshold-based scoring. It had no tests, no `.env.example`, no starter bank, no durable storage abstraction, and no independent adaptive states.

## Confirmed weaknesses

- **Crude adaptation:** `get_level_decision()` moved a single ILR label after fixed block-score thresholds rather than estimating ability.
- **Shared diagnostic state:** combined Reading and Listening alternated blocks while sharing `current_level`, `recent_block_scores`, and one adaptive path.
- **Ignored controls:** `target_level`, `timer_mode`, and `base_session_questions` were stored but did not affect selection, timing, or stopping.
- **Answer leakage:** prompt examples explicitly prescribed Q1=A, Q2=B, Q3=C, Q4=D in generation, repair, and audit prompts.
- **Fixed four-question UI:** rendering, scoring, progress, and submission assumed exactly four questions.
- **Live-generation-only operation:** every passage required a hosted model call; provider failure prevented testing entirely.
- **Fragile parsing:** model output was recovered by taking the first `{...}` substring and decoding permissively.
- **Uncalibrated labels treated too strongly:** LLM-assigned ILR labels drove adaptation as if they were psychometric difficulty.
- **Synthetic TTS lifecycle gaps:** final temporary MP3 files accumulated; replay restrictions were advisory only.
- **No durable recovery/history:** no checkpoint restore, user exposure history, duplicate prevention, or downloadable raw session export.
- **Insufficient evidence reporting:** the report could assign a half-level from four items at a band and did not report uncertainty.
- **Mixed UX:** training speed/voice controls coexisted with diagnostic behavior, and strict navigation/timing were not implemented.
- **Dependency drift:** requirements used broad lower bounds while Space metadata declared a specific Gradio release.
- **No automated tests:** core psychometrics, shuffling, timers, playback, persistence, and launch behavior were unverified.

## Resolution

The release replaces these behaviors with typed models, an item-bank-first design, independent Bayesian skill estimates, variable bundles, code-side answer shuffling, strict mode enforcement, checkpoint recovery, validated starter content, pinned dependencies, and a 63-test suite. The subsequent GenAI overhaul also restored the useful original provider configuration and level-specific authoring concepts through a safer staged schema/audit/repair/verification pipeline; see `GENAI_AUDIT.md`.
