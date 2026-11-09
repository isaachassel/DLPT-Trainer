# Lesson 32 vocabulary practice

This local-only batch is on `codex/russian-vocabulary-study`. The published
assessment demo is unchanged.

## Use it

Start `study_app.py` with the project virtual environment and open
<http://127.0.0.1:7864/>. Create or sign in to your local profile. Choose:

- Vocabulary collection: **Course modules**
- Module / group: **Mod 6**
- Lesson: **Lesson 32**
- Skill: **Reading** or **Listening**

Select **Start vocabulary check** for 2–5 passages. Each passage checks six
meanings in context with four choices and an **I don't know** option. Mark
guesses honestly. Answers and listening transcripts appear when the check ends.
Then select **Review my weaker words**. Short reading examples provide a fresh
context; listening review reuses the dialogue and allows unlimited replays.
The usual new-card daily allowance still applies. **Start review** also lets you
study the covered words directly without taking a check.

## Content and scope

Eight newly authored fictional dialogues check **48 of the 80 Lesson 32
word-and-meaning entries** in the local course import, with 48 separate short
reading examples. The two meanings of `носить` count separately. Coverage is
explicit; the other 32 entries are not assessed by this batch.

Topics: military museum exhibits, supplies in an archive collection, motion
verbs while preparing an exhibition, orders in a historical letter, contrasting
historical accounts, checking family records, and revising a fictional news
summary. Questions test contextual vocabulary recognition rather than memorized
English glosses alone. They do not establish general passage comprehension or
a DLPT level. The existing study stages 1–3 describe practice complexity, not ILR.

Reference: the user-supplied *Russian Basic Course, 2018 validation edition,
Module VI, Lessons 32–33*, Lesson 32 glossary, printed pp. 85–88 (PDF pp. 93–96).
Vocabulary/senses were checked against the glossary and the imported course list.
The textbook, its illustrations, source readings and existing exercises are not
reproduced in the bank or sent to ElevenLabs. Only the original Russian dialogue
scripts are submitted for synthesis. The local source extraction and coverage
audit remain under ignored `storage/workshop/lesson32/`.

Language/questions are provisional authored study material; no DLI endorsement
or independent native-speaker review is claimed. Audio uses the owner's standing
approval of the Jessica/Eric Eleven v3 method. Automated decoding and browser
playback checks do not substitute for a pronunciation review.

## Rebuild and generation

`scripts/lesson32_study.py` holds the original authoring source. Run:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_vocabulary_passages.py
.\.venv\Scripts\python.exe scripts/generate_study_audio.py --batch lesson32
# Explicit operator action, consumes credits only for ungenerated scripts:
.\.venv\Scripts\python.exe scripts/generate_study_audio.py --batch lesson32 --generate
```

The batch contains **4,541 input characters**, capped at 8,000. Preflight confirmed
a paid Starter plan and 54,113 available credits. At the checked model rates the
conservative maximum debit is 4,541 credits. There are no purchases, plan changes
or automatic uncertain retries. A separate resumable ledger at
`storage/workshop/lesson32-20261108/ledger.json` reserves each request before
generation. A shared study-generation lock prevents overlapping batch runs.
Publication verifies the staged files and merges their records into the audio
manifest, retaining the previous nine recordings and all other study contexts.

Model: `eleven_v3`; voices: existing premade Jessica and Eric. Official
[model release status](https://elevenlabs.io/blog/eleven-v3-is-now-generally-available)
and [paid-plan publishing terms](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform)
were checked on November 8, 2026. Checksums, script fingerprints, plan, generation
date and licensing provenance are recorded in `data/study/audio.json`.

All eight MP3s decoded successfully: 36.4–43.9 seconds each, 5.23 minutes total.
The settled account count increased from 2,084 to 3,901: **1,817 credits used**,
leaving **52,296 credits**. All nine previous recording records and files were
preserved. Total context coverage is now 370 imported entries for reading and
235 for listening; these are entry counts, including repeated senses across
course collections, rather than unique headwords.

## Verification

The lesson regression tests cover 48 distinct sense links, both skills, lesson
filter isolation, carry/wear separation, missed/guessed words entering review,
separate skill histories, disjoint generation batches, budget bounds and safe
manifest merging. Existing tests cover question visibility, grading, scheduling,
answer withholding, profile isolation and recording decoding/provenance.

On November 8, 2026, the focused suite passed **54 tests**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_lesson32_study.py tests/test_vocabulary_check.py tests/test_vocabulary_study.py tests/test_demo_hosting.py tests/test_audio_release.py -q
```

Browser QA used a separate `Lesson 32 QA` profile, leaving learner histories
untouched. Verified Mod 6 / Lesson 32 shows 48 cards per skill; all six questions
have choices; a complete 37-second listening playback; submission and the next
passage; a report with one miss and one guessed correct answer; and the weaker
word review opening `везти` with its recording. Reading displays the original
dialogue beside the choices. The test profile was signed out afterward. Screenshot:
`storage/exports/lesson32-study-preview.jpg` (local, ignored by Git).
