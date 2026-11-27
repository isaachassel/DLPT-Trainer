# Codex import instructions — Reading Pilot 01

Implement the attached `reading_bank.json` as a static reading content pack in the existing adaptive DLPT trainer. Inspect the repository's instructions and current content schema first. This is a portable interchange schema, not a claim about the repository's native schema.

## Required behavior

1. Map the six passage records and 18 questions into the app's existing model with stable IDs. Keep original records or a lossless mapping so provenance, rights, evidence, and review status survive. No duplicate imports on a second run.
2. Preserve Russian text exactly, including qualifiers and documented source errors. Paragraph IDs are presentation aids. The source headline is metadata, not a learner-facing title; several headlines reveal answers. Use neutral labels such as Reading passage 1 and show publication dates.
3. Store this bank locally or in the application's content storage. Running these preset passages requires no ElevenLabs account, AI provider account, API key, or generation request. Public assessment playback of already-cleared preset audio should likewise be independent of generation credentials; this pack adds reading content only.
4. Import as teacher-review drafts. Provide instructor preview or the existing draft review flow. Do not silently mark these items teacher-approved or calibrated. Once reviewed, activate them through the app's normal content approval process. Existing approved diagnostic content should keep working.
5. Keep answer keys, evidence, explanations, and difficulty rationale out of the learner's pre-submission assessment response. If the app uses a backend, score there. Do not ship the entire authoring JSON in a public diagnostic bundle. A static-only implementation cannot securely conceal bundled answers; describe that limitation if it applies.
6. Show source attribution and license links accessibly without making the original headline an answer cue in the assessment view; for example, use a Source and license disclosure with full credits. Include original publisher and archive attribution, date, license, and the excerpt/formatting-change notice. Do not imply source or NFLC endorsement.
7. Keep all questions attached to their passage. Persist stable option IDs if answer choices are shuffled. Use passage-family exposure tracking so an already-practiced passage does not later appear as fresh diagnostic material for that learner. Do not treat three questions on one passage as three independent proficiency observations.
8. Retain provisional_ilr as author metadata, not an empirical difficulty parameter. Do not invent IRT parameters or convert this small pilot's raw score into a validated DLPT/ILR score. A draft preview can report raw correct/total and the skill categories missed.
9. Preserve the distinction between authentic passages and any future generated drills. Do not simplify these source texts with an LLM during import. Do not label synthesized narration of an article as an authentic interview.
10. Add or use meaningful import validation: unique IDs; exactly four distinct choices; one valid key; evidence quotations present in their referenced paragraphs; provenance and licensing retained; drafts excluded from production diagnostics; unauthenticated preset reading works without generation credentials. Use existing test conventions rather than introducing a new test framework.

## Files

- reading_bank.json: complete authoring data, keys, rationales, and source records.
- reading_review.md: learner copy followed by the teacher key, provenance, and review rubric.
- validation_report.json: structural checks performed while assembling this pack.

## Teacher approval

Ask the Russian teacher to check authenticity, appropriate passage difficulty, unique best answers, plausible distractors, and exact evidence. Record reviewer identity, approval date, and revisions. If wording changes, bump the content version and preserve the prior record. Set diagnostic eligibility only through the project's existing approval rules. Approval does not substitute for empirical calibration.

## Completion report

Explain the schema mapping, where the bank lives, how an instructor previews and approves it, what an uncredentialed learner can run, and which validations passed. Report any schema or deployment limitation. Do not expand this task into ElevenLabs integration or listening-source collection.
