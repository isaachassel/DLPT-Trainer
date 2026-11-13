# ALES assessment and study

Branch: `codex/ales-study`, based on `codex/lesson-study` at `c5a9a61`.
This is a local study feature. The live Hugging Face/WordPress demo is unchanged.

## Use

Run `.venv/Scripts/python.exe study_app.py` and open <http://127.0.0.1:7864/>.
Sign into an existing profile (or create one), click **Study ALES words**, and
choose Reading or Listening. Choose 2–15 passages, then **Start ALES assessment**.
Each passage has four questions whose answer depends on a target glossary word.
Select an answer or **I don’t know**; mark uncertain correct answers as guesses.
Listening permits replays for study. Keys and transcripts appear after the check.

The report separates **Correctly recognized without guessing** and **Words to
work on again**. Click **Review my weaker words** to practice missed/guessed
words. Reading reviews use a different short example. Listening reviews reuse
the complete recorded dialogue. Rate recall honestly to schedule subsequent
reviews. Existing daily new-word limits still apply.

The ALES dashboard shows cumulative latest recognition results separately for
reading and listening. The word list and progress export use the same profile
database as the original vocabulary features. Profiles remain local to this
computer; this does not introduce cloud account synchronization.

## Coverage and interpretation

The supplied CSV imported **474 rows / 474 distinct headword-sense entries**.
All entries are available for reading word review: uncheck context-only and use
**Start review**. The initial authored passage bank contains **15 dialogues,
60 comprehension questions and 60 fresh short review contexts**, covering
**60 of 474 entries** in both reading and listening. The remaining **414 entries
do not yet have authored passage/audio coverage**. Coverage counts are shown
in the interface and report. Completing every current passage does not test the
entire glossary. No unit assignments are guessed or used to organize ALES study.

Topics include weather, travel, employment, budgets, diplomacy, research,
elections, rules, relief, aviation, shipping, courts, science, sport and news.
These are original synthetic learning materials, not authentic SLS/DLI items.
Language, distractors and pronunciation remain provisional pending instructor
review. Each target is linked by exact source headword AND English sense.
Homographs with different meanings retain different IDs.

The existing check selector starts with stage 1, moves up after at least 80%
confidently correct responses, and down after at most 50%. Stages describe these
authored contexts, not ILR levels. Selection favors prior weaker/unseen words
among similarly staged passages. No passage repeats within a check. A longer
test ends at the selected length or when matching content is exhausted; a learner
can stop early. A single recognition answer never marks a card as mastered.
Repeated checks of the same word/skill/passage replace its latest observation
rather than manufacture independent evidence. The inherited word-evidence model
accounts for four-choice guessing and discounts self-reported guesses; its broad
uncertainty is not presented as a validated proficiency score.

ALES results remain in a server-side check snapshot until completion or an
explicit early stop. Only then are they published to profile evidence and review
priorities in one transaction. Replacing an unfinished check discards its pending
results; the interface does not reveal them mid-test through history/export.
Already submitted results are idempotent on retry. Tests are bound to a profile
and login. A newer observation is not overwritten by an older in-flight check.
Self-rated later reviews preserve their history and scheduling.

## Import and authoring

```powershell
.venv/Scripts/python.exe scripts/import_ales.py 'C:/Users/isaac/Downloads/ALES_Units_1-15_Glossary.csv'
.venv/Scripts/python.exe scripts/prepare_ales_passages.py
.venv/Scripts/python.exe scripts/generate_study_audio.py --batch ales
```

The importer reads UTF-8 CSV (with or without BOM) using the five original
column names. It preserves supplied source metadata but never fills blank item,
lesson or unit values from neighboring rows. Russian + English sense determine
stable namespaced IDs independent of row order. Duplicate identical senses merge
source references. Invalid input fails before writing an import.

The original CSV is untouched. Its full imported glossary is stored in ignored
`storage/vocabulary/ales.json`; it is not published or committed. Other machines
need to import their own copy. Profile databases, generation ledgers and `.env`
also remain ignored. Only authored passages/questions, generated recordings and
their internal provenance are versioned.

Add original passage specs to `scripts/prepare_ales_passages.py`. Each target
needs the exact CSV entry/sense, a spoken form occurring in the dialogue, one
correct contextual answer, three distinct plausible alternatives, a comprehension
question and a separate short review sentence. Avoid questions solvable from
topic alone or a different sentence that translates the target. The builder
emits `data/study/ales/passages.json`; runtime linking uses explicit word IDs,
not fuzzy matches to similarly named course words. No existing course IDs change.

## Audio batch, 2026-11-13

15 MP3s use the previously approved Jessica/Eric method with `eleven_v3`, under
the current Starter subscription. **3,984 unique input characters** were used.
The observed provider counter rose from **3,901 to 5,383**: **1,482 credits net**,
leaving **50,814** at the final check. Counter changes are provider observations,
not a guarantee of future pricing. No credits or subscription upgrades were bought.

Two requests lost their connection. Each was reviewed against the subscription
counter before one bounded retry; the counter accounted only for completed
recordings at those checks. API history retrieval lacked permission. Original
reservations remain in the ignored ledger and count against the 8,000-character
cap (4,530 characters reserved including both interrupted requests). Completed
files were reused, not regenerated. Every MP3 decoded and passed checksum and
script-fingerprint validation before publishing the whole batch locally.

Internal provenance is in `data/study/ales/audio.json`. Commercial-plan and model
status were checked against the official
[publication guidance](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform)
and [Eleven v3 general availability announcement](https://elevenlabs.io/blog/eleven-v3-is-now-generally-available).
No claim of individual human listening review is made.

## Verification

70 focused tests passed (16 ALES tests plus 54 existing study regressions).
They cover import validation and sense identity, all authored links,
strong/weak/mixed/guessed performance, all 15 passages without repeats, sparse
banks, early stopping, hidden pending results, retries, profile/skill isolation,
review scheduling, persistence/export, audio provenance and decoding. Existing
vocabulary, Lesson 32 and competency-mapping regression tests also pass.

Browser checks use a disposable local QA profile. They verify reading passage
progression, report grouping, profile counts, a weaker-word review and saved
rating, plus listening playback and withheld transcripts. Screenshot evidence is
stored locally in `storage/exports/ales-study-report.jpg` and is not committed.
