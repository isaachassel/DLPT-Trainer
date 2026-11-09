# Russian vocabulary study (local preview)

Branch: `codex/russian-vocabulary-study`, based on the published demo branch.
The existing `app.py` and public assessment remain unchanged. Start the study
preview with the project's existing virtual environment:

```powershell
cd C:\Users\isaac\Projects\DLPT-Trainer
.\.venv\Scripts\python.exe study_app.py
```

Open <http://127.0.0.1:7864/>. Create your own profile, choose Reading or
Listening, and select **Start review**. The second tab keeps the existing
Russian/Chinese adaptive assessment available. Study answers do not affect
assessment scores or history.

**Lesson 32 expansion:** select **Mod 6 → Lesson 32** for eight new dialogue
checks covering 48 course word senses, with reading and ElevenLabs listening
practice. See [Lesson 32 setup, coverage and generation notes](LESSON32_STUDY.md).
The counts below describe the earlier pilot; the linked notes describe this batch.

For the new assessment-to-review flow, select **Start vocabulary check** first.
It checks up to six words in each of 2–5 longer passages (three by default), then
offers **Review my weaker words**. Use All modules/lessons initially: the pilot
does not yet have passage checks for every lesson. The existing direct review
button is still available. Refresh an already open browser tab after updating.

## What is ready

- Persistent local profiles with salted scrypt password hashes, expiring login
  sessions, and separate reading/listening review histories.
- Module, lesson and collection filters; due cards before new cards; up to ten
  cards in a session. A shared daily allowance defaults to ten new word/skill
  cards. Set it to zero to review only previously introduced cards.
- Short Russian reading contexts and short approved listening dialogues.
  The target word is identified; the learner types an English guess before
  revealing its meaning and, for listening, the transcript.
- Again / Hard / Good / Easy self-ratings, saved next-review dates, and a
  searchable list of New, Learning, Shaky and Well known entries.
- A JSON progress export under **My vocabulary & progress**. This is a
  human-readable record, not an import/restore format in this first version.

The learner judges equivalent English meanings; there is no automatic semantic
grading or provider call. **I don't know** requires an Again rating. Skipping or
finishing an unrated card does not change its schedule. Rating retries are
idempotent; stale ratings from another login are rejected. Filters apply to the
next session, not the active card. A word does not repeat in the same session;
an Again card becomes available in another session after ten minutes.

## Workbook and coverage

The read-only importer takes columns A–D (group, lesson, Russian, English) from
the workbook's combined `всё слова` sheet. It does not execute formulas, macros,
speaker links, or instructions inside the workbook. Embedded images are not
copied. Equivalent word-and-definition rows merge while preserving every source
row, module and lesson; different definitions remain separate entries.

```powershell
.\.venv\Scripts\python.exe scripts/import_vocabulary.py "P:/PCloud/Professional Development-Education/DLI/RU01125.xlsx"
```

Restart the app after importing. The current source has 8,462 complete rows and
7,765 distinct word-and-meaning entries: 2,618 source rows in modules 1–7, plus
ALES, themes and a frequency list. The default filter uses the course modules.
The workbook and imported list remain local and excluded from Git.

Current pilot context coverage:

| Collection | Entries with reading context | Entries with listening context |
|---|---:|---:|
| Course modules | 175 | 102 |
| All imported vocabulary | 295 | 160 |

There are 270 context exercises: the original 162 plus 54 fresh short reading
contexts and 54 word links to nine new longer dialogues. Multiple dictionary entries may share
an exercise, so these are entry counts, not unique headword or passage counts.
Listening uses **14 existing approved Russian recordings** and **nine new paid-plan
recordings**, each 31–48 seconds. The new batch used 5,208 input characters and
2,084 settled credits, leaving 54,113 credits at the post-run check. No purchases
or subscription changes were made. Study allows unlimited replays; the assessment
tab retains two listens with a beep. See [batch provenance](VOCABULARY_EXPANSION.md).

Coverage is intentionally explicit: only words with context appear by default.
Uncheck **Only words with context** to use word-only reading reviews from the
remaining course list. Listening never silently falls back to a written card.
New original examples are provisional study content, not claimed to have DLI or
human linguistic approval. English senses and Russian target forms are linked
explicitly; automated linking does not establish expert validation.

## Scheduling approach

This is a transparent interval ladder inspired by the self-rating workflow of
[Anki](https://docs.ankiweb.net/studying.html), **not Anki's algorithm or FSRS**.
It is not a calibrated memory/retention model.

- Good advances one step: 1, 3, 7, 14, 30, 60, 120, 180 days.
- Easy advances two steps (a first Easy review is due in three days).
- Hard steps back once and halves the previous interval, bounded to 6 hours–7
  days. A first Hard review is due in six hours.
- Again resets the ladder, increments lapses, and is due in ten minutes.
- Shaky means the latest response was Again or Hard. Well known requires a
  scheduled interval of at least 30 days and successful recall on at least three
  distinct local review dates since the last Again/Hard. Other reviewed cards
  are Learning. Repeated clicks on one day cannot establish Well known status.

Intervals are elapsed hours/days; daily new-card limits follow the profile's
chosen timezone and daylight-saving transitions. A reading card and a listening
card for the same vocabulary entry each count toward the daily new-card limit.
These labels summarize self-reported practice, not language proficiency.

## Passage checks and personalized review

Each new dialogue checks six specific meanings with four shuffled choices plus
**I don't know**. **That was a guess** preserves a correct answer in the raw score
but puts the word in the review plan. All answers and listening transcripts remain
hidden until the check ends. Incomplete submissions do not update evidence.

Passages have three provisional study stages, not ILR labels. The check begins at
stage 1. At least 80% correct without guessing raises the next stage; at most 50%
lowers it; other performance holds the stage. Within the closest available stage,
selection prefers previously flagged words, then untested words. No passage
repeats within a check. It stops at the selected length, at content exhaustion,
or when the learner ends it; reports distinguish these reasons. Narrow filters
can leave fewer than two passages or no suitable checks; no missing vocabulary
is silently scored.

Evidence is stored separately per profile, skill, word sense and passage. A
uniform grid prior for a word's recognition probability is updated using
`P(correct | recognition) = 0.25 + 0.75 × recognition`. A correct answer marked as
a guess contributes one-quarter likelihood weight. The latest observation for
the same passage replaces the earlier one rather than multiplying evidence.
The internal mean and 90% interval remain broad after one observation. These
are heuristic, uncalibrated practice estimates, not validated retention or DLPT
scores; the interface deliberately uses plain review guidance instead of
presenting precise-looking word probabilities.

Six words in one passage are six separate word observations; they are not pooled
as independent evidence of one overall ability. A single correct answer never
marks an entry Well known. Untested words stay unassessed. Additional independent
contexts are still needed for stronger conclusions about each word.

Missed/guessed words lead the new-card queue, followed by unchecked words and
then words answered correctly. Due reviews still precede new cards. A miss on an
already introduced word makes it due now without deleting prior reviews. The
focused-review button selects only weaker due/new cards and respects the daily
new-card allowance. Reading uses a fresh short context; listening can reuse the
longer recording, so listening follow-up is reinforcement, not an independent
retest. A successful later self-rated review resolves immediate diagnostic
priority but preserves the check evidence and future schedule. The answer report
is cleared when focused review starts.

## Local data and maintenance

- `storage/vocabulary/course.json`: imported vocabulary, source checksum,
  provenance, and import report (ignored by Git).
- `storage/study/profiles.sqlite3`: profiles, password hashes, session-token
  hashes, typed guesses, schedules, and review history (ignored by Git).
- `data/study/contexts.json`: original study contexts and references to approved
  project audio; contains no imported course dictionary.
- `data/study/passages.json`: nine original passage checks, target senses,
  distractors and fresh short contexts. It contains no imported workbook file.
- `data/study/audio.json` and `audio/`: checksum-bound paid-generation provenance
  and the nine new MP3s. Only these assets are added to the local file allowlist.
- `scripts/prepare_vocabulary_passages.py`: offline authoring source for the new
  passages. Rebuild the JSON after edits; changed scripts invalidate old audio.
- `scripts/generate_study_audio.py`: explicit operator CLI; the web app never
  generates audio or consumes credits. Without `--generate`, it only preflights.
  Its ledger reserves spend before each request, skips completed matching assets,
  refuses uncertain retries, caps the batch at 8,000 input characters and
  publishes the audio manifest only after all files decode successfully.
- `scripts/prepare_study_contexts.py`: reproducible offline context builder.
  Append new contexts without renumbering existing IDs. Run the script after
  editing and restart the app. Contexts require a target found in the passage,
  an explicit dictionary headword, English sense hints and a contextual meaning.

The server binds only to loopback, disables public sharing, blocks file serving
of private study data, and refuses to start in Hugging Face hosted mode. This is
not a hardened public account system: no email recovery, cloud sync, account
management, or encrypted database. Someone with access to your Windows files
can read study history. Do not expose this preview through a tunnel.

For a complete backup, stop the study server and copy both private storage
folders to your own secure backup. Restoring those folders restores profiles and
history; keep the same vocabulary IDs. The password is needed after restoration.
Do not commit the workbook, imported dictionary, database, exports or `.env`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_vocabulary_check.py tests/test_vocabulary_study.py tests/test_content_intake.py tests/test_demo.py tests/test_demo_hosting.py tests/test_demo_reporting.py tests/test_audio_release.py -q
```

Tests cover workbook deduplication/provenance and formula skipping; Unicode
normalization; progress persistence and profile separation; grading guards;
duplicate/stale submissions; daily limits, due priority and timezone boundaries;
skill separation; sparse banks; answer/transcript withholding; audio reuse;
local-only launch configuration; and coexistence with the assessment UI.

On November 4, 2026, the targeted suite passed **77 tests**. Browser verification
covered creating a profile, retaining a review across a server restart and
sign-in, reading answer reveal, a complete 22-second listening playback,
transcript reveal, Hard/Again scheduling, next-card progression, session finish,
and opening an assessment passage from the second tab. Screenshots are saved
locally under `storage/study/` and excluded from Git. The `Preview check` profile
contains only disposable verification progress; create your own profile to study.

The expansion adds tests for strong, weak, mixed and borderline routes, guessed
answers, repeated-context deduplication, word-level uncertainty, missing answers,
retry safety, profile/skill isolation, sparse banks, stopping, focused reviews,
daily limits, existing-card history preservation, new audio decoding and checksum
provenance. Browser checks use a separate `Passage QA` profile and never modify
the learner's profile. Nothing in this expansion is deployed to the live demo.
