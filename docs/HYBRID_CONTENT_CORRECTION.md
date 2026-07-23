# Hybrid Content Correction

The previous release interpreted “item-bank-first” too narrowly and removed user-session generation from the operational path. That improved reliability but unnecessarily discarded a useful feature of the original application.

The corrected architecture treats these as complementary capabilities:

- **Live generation creates new content when the learner requests it.**
- **Validation determines whether that content is safe to use.**
- **The generated-bank overlay preserves accepted content for reuse.**
- **The combined bank provides immediate fallback when generation is unavailable or exhausted.**

Fresh generation is therefore optional, constrained, rate-limited, validated, and non-destructive. The bank remains the reliable baseline and accumulated memory rather than the only content source.


The v1.2 release further replaces the short all-in-one live prompt with separate passage authoring, passage audit, question authoring, blind verification, repair, Python shuffling, and atomic persistence stages. See `GENAI_AUDIT.md`.
