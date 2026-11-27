# Authentic Russian reading pilot

Implemented on `codex/authentic-reading-pilot`, based on the deployed
`codex/sls-assessment-pilot` branch. The ALES branches are preserved. No live
Space, WordPress page, GitHub branch or production bank has been changed by
this import.

## Content and provenance

`data/content_packs/ru-authentic-reading-pilot-01/package.json` contains six
teacher-review drafts and 18 questions. The source pack suggests two passages
at 1+ and four at 2. These are author judgments, not calibrated item parameters.
No new reading or listening generation is involved, and no API keys are needed.

The original `reading_bank.json` is retained byte-for-byte under `versions/v1/`.
Each native item also carries its entire original record in `authoring_record`,
including paragraph IDs, all evidence quotations, every distractor rationale,
rights evidence, transformations, review status and difficulty rationale.
The supplied `CODEX_IMPORT.md`, `reading_review.md` and `validation_report.json`
are retained beside the native package. The standalone supplied review file
matches the ZIP copy.

On November 27, 2026, all six fixed Wikinews archive revisions loaded over
HTTPS. Each included an article-specific CC BY 4.0 notice identifying the
original publisher. All supplied paragraphs matched after whitespace
normalization and removal of two documented archive-added Wayback annotations.
The imported Russian text was not rewritten. Checks and archive hashes are in
`source_verification.json`. This verifies the archive's statements, not the full
original rights chain or the truth of historical claims. Teacher review remains
required; the archived articles themselves are marked as bot imports.

## Instructor preview and approval

From the project root in PowerShell:

```powershell
.venv/Scripts/python.exe scripts/preview_reading_pack.py --port 7866
```

Open <http://127.0.0.1:7866/>. Choose a neutral numbered passage, click **Open
passage**, answer all three questions, and click **Finish preview and review**.
The result shows raw correct/total, missed skill categories, the answer key,
paragraph evidence, distractor rationales and full source/license links. It
does not estimate proficiency or approve anything. It binds only to localhost;
the preview is deliberately excluded from the public deployment.

Give the Russian instructor `reading_review.md` for offline review. Ask them
to check authenticity, passage difficulty, a unique best answer, plausible
distractors and exact evidence. Record their name, date, revisions and explicit
reuse attestation. Existing automatic approval of generated audio does not
approve these new reading questions.

After receiving that review, the local curator can activate each approved item
through the existing CLI, for example (replace the example reviewer/notes):

```powershell
.venv/Scripts/python.exe scripts/curate_assessment.py validate --package data/content_packs/ru-authentic-reading-pilot-01/package.json
.venv/Scripts/python.exe scripts/curate_assessment.py approve --package data/content_packs/ru-authentic-reading-pilot-01/package.json --item ru-read-pilot01-museum --reviewer "Actual teacher name" --notes "Actual review findings and revisions" --attest-reuse-rights
```

Approval writes a dated named review into `data/assessment/bank.json`; it does
not deploy. The native `review` controls eligibility; draft flags inside the
immutable original record continue to describe its original submission status.
Restart the app after approval. Updating already approved content
requires a higher `content_version` and fresh review. Prior approved wording
and decisions are preserved under `data/assessment/revisions/`.

For a revised source pack, use the importer with a higher version:

```powershell
.venv/Scripts/python.exe scripts/import_reading_pack.py path/to/revised-reading_bank.json --output data/content_packs/ru-authentic-reading-pilot-01/package.json --version 2
```

Importing the identical file/version again is a no-op. A changed source cannot
overwrite an immutable archived version. Imports always produce drafts; they
never modify the active manifest or trigger generation.

## Runtime mapping and learner behavior

- Original passage/question IDs and family IDs are stable. A–D are stable source
  option IDs; randomized display letters are mapped back to those IDs in each
  response. The fine-grained author skill is retained alongside the closest
  native question category.
- Native `target_ilr` and `provisional_difficulty` use the existing uncalibrated
  routing heuristic. No IRT parameters are invented and all calibrated fields
  remain null. The existing passage-level evidence discount and guessing model
  are unchanged. The three questions travel together, even if this slightly
  exceeds the requested question count at the end of a mixed bank test.
- Published dates and neutral labels appear during reading. Headlines, source
  links, keys, explanations and difficulty rationales stay off the active
  learner screen. At the end, **Sources for your reading** shows original title,
  publisher, byline information, publication date, original URL, fixed archive
  revision, CC BY link, excerpt/formatting notice and non-endorsement disclosure.
  Credits are snapshotted when a passage is shown, so timeout/early-stop reports
  also credit displayed material and later bank edits cannot change old credits.
- All existing approved reading/listening presets still run without generation
  credentials. New drafts are unavailable to diagnostics until approved.
- Family exposure is recorded on display, including unanswered previews. For
  an identified local profile, use the same profile ID in the preview and the
  diagnostic: the history excludes all versions of that family. Anonymous demo
  users have same-browser family memory. Clearing storage, changing origin or
  device, or using an unrelated local profile cannot be reliably linked; this
  demo has no cross-device learner identity. Instructor preview on port 7866
  cannot automatically identify that person in the anonymous hosted demo.
- Exhausting unseen authentic families never silently resets their exposure.
  The test ends for lack of eligible content, or refuses to start if the chosen
  initial band has no eligible passage. Synthetic practice's prior behavior
  remains unchanged.

## Deployment and confidentiality

The server scores answers and retains complete bundles in Gradio server state.
The browser receives displayed passage/question/choice text, not the authoring
record. Gradio file routes block the native manifest and draft pack. Deployment
packaging excludes draft items, original interchange/review files and revision
archives; approved items omit the redundant `authoring_record` from the server
ZIP but retain operational keys and attribution. Maintain the Protected Space
repository setting: a publicly downloadable repository/deployment ZIP would
make its backend answer keys readable. This is a training tool, not a secure
high-stakes examination service.

The regression suite passed 175 tests. Test coverage includes exact text/evidence, invalid inputs, idempotency,
version preservation, explicit approval, draft isolation, complete question
groups, shuffled keys, same-family exclusions, safe end-only credits,
credential-free approved-fixture assessments and existing demo regressions.
Browser QA completed a draft with 3/3, verified all three choice groups and
post-submission source links. Local screenshot:
`storage/exports/authentic-reading-source-review.jpg`.
The preview's authoring-file URLs returned HTTP 403; its initial configuration
contained no answer keys or evidence. A local deployment build retained the
existing 66 approved items and 38 recordings and excluded all six new drafts.

Publishing requires teacher approval for content and the user's deployment
approval. Until then, the existing hosted adaptive demo stays unchanged.
