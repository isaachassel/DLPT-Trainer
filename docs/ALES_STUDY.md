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
**Start review**. The expanded authored passage bank contains **95 dialogues,
380 comprehension questions and 380 fresh short review contexts**, covering
**380 of 474 entries** in both reading and listening. The remaining **94 entries
do not yet have authored passage/audio coverage**. Coverage counts are shown
in the interface and report. Completing every current passage does not test the
entire glossary. No unit assignments are guessed or used to organize ALES study.

Topics include weather, travel, employment, budgets, diplomacy, research,
elections, rules, relief, aviation, shipping, courts, science, sport and news.
The second batch adds museum visits, youth programs, rail services, housing,
manufacturing, financial reporting, education, environmental surveys and more.
The third batch adds family descriptions, community events, publications,
workplace decisions, travel, science, diplomacy and local administration.
The fourth batch adds visits, walking routes, chess, event planning, restoration,
river travel, museum interviews, public announcements and incident reporting.
The fifth batch adds neighborhood events, guest visits, instrument settings,
maintenance, training, surveys, historical displays and collection catalogs.
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

The `ales` audio batch selects only the original 15 dialogues. Use `--batch ales2`
to preflight the 20-dialogue expansion; append `--generate` only when authorized
to spend provider credits. Use `--batch ales3` for the third 20-dialogue batch and `--batch ales4` for the fourth, and `--batch ales5` for the fifth. Separate ledgers keep earlier batches unchanged.

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

Add original passage specs to `scripts/prepare_ales_passages.py` or its imported
`scripts/ales_expansion.py`, `scripts/ales_expansion3.py`, `scripts/ales_expansion4.py` or `scripts/ales_expansion5.py` batches. Each target
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

## Audio expansion, 2026-11-22

Added 20 dialogues and recordings for 80 previously uncovered senses, retaining
the original 15 passages and recording records unchanged. The new batch uses
the same approved Jessica/Eric voices and generally available `eleven_v3` model
under Starter. It consumed **5,033 unique input characters**, below its separate
8,000-character reservation cap, with no failed requests or retries. All 20
recordings decoded and matched their script fingerprints before local publication.

The provider counter was **5,494 before generation** and **7,507 at the later
verification**, an observed increase of **2,013 credits**, leaving **48,690 of
56,197**. The immediate post-generation counter was lower; provider counters can
settle asynchronously. These are observed account snapshots, not guaranteed
per-request prices. No purchase, upgrade or live deployment was performed.
Detailed reservations and account snapshots remain in the ignored
`storage/workshop/ales-20261122/ledger.json`; recording provenance is versioned
in `data/study/ales/audio.json`.

## Audio expansion, 2026-11-23

The third batch adds 20 original dialogues for 80 more distinct senses. All
35 earlier passages and their audio provenance are preserved. Each new dialogue
has four vocabulary-dependent questions and four separate short reading-review
contexts. The bank now has 55 dialogues covering 220 of 474 entries (254 remain).

The batch uses **5,327 unique input characters** with the approved Jessica/Eric
voices and `eleven_v3` under Starter. One request stalled during a connection
interruption and was stopped. Its charge could not be excluded: usage counters
settle asynchronously and history retrieval was unavailable to the configured
key. After the user reported reconnection and requested another attempt, one
explicit bounded retry was made. The interrupted request's 271 characters remain
in the budget ledger: **5,598 reserved characters including the retry**, below
the 8,000-character cap. Completed recordings were reused, not regenerated.
The audit ledger is ignored at `storage/workshop/ales-20261123/ledger.json`.
No subscription change, purchase, GitHub push or public deployment is included.

All 20 MP3s decoded and passed script-fingerprint and checksum checks before
the complete batch was activated locally. The provider counter rose from
**7,507 to 9,747**, an observed **2,240 credits**, leaving **46,450 of 56,197**.
This later snapshot includes the interrupted request and retry; exact individual
request billing could not be verified through history. The immediate completion
counter was lower, so later-settling provider counters remain the authority.

## Audio expansion, 2026-11-24

The fourth batch adds 20 original dialogues and 80 previously uncovered senses,
with four questions per dialogue and 80 separate short reading-review contexts.
All earlier 55 passages remain unchanged. A snapshot regression checks their
content; batch-selection checks keep generation separate from earlier recordings.

Scripts total **5,266 input characters**, within the separate 8,000-character
batch cap. The same Jessica/Eric voices and generally available `eleven_v3`
model are used under Starter. Reservations and provider account snapshots are
kept in ignored `storage/workshop/ales-20261124/ledger.json`. Language and
pronunciation are provisional; technical validation is not instructor review.
The live demo is unchanged; this batch is local to the ALES study branch.

All 20 recordings completed without retries and passed decoding, checksum and
script-fingerprint checks before activation. They total approximately 357 seconds.
The later provider snapshot rose from **9,747 to 11,853** used credits: an
observed **2,106 credits**, leaving **44,344 of 56,197**. Counters can settle after
requests finish; this is an observed batch total rather than per-request billing.

## Fifth audio batch, 2026-11-24

Added 20 original dialogues, 80 vocabulary-dependent questions, and 80 separate
short reading-review contexts for previously uncovered senses. All 75 earlier
passages and audio records are preserved. The bank now contains 95 dialogues
covering 380 of 474 entries in both reading and listening; 94 entries remain.

The approved Jessica/Eric voices and generally available `eleven_v3` model were
used under Starter. Scripts total **5,166 unique input characters**. The first
235-character request was interrupted before its audio could be saved; the
provider counter increased by 94 credits. History retrieval was rejected by the
configured key, so recovery was unavailable. One bounded retry was made after
reviewing the balance and recording the possible duplicate charge. The original
reservation remains in the ledger: **5,401 reserved input characters**, below
the separate 8,000-character cap. No completed recording was regenerated.

All 20 final MP3s decoded and passed checksum and script-fingerprint validation
before publication into the local bank. Total new audio duration is **351.6
seconds**. The later provider snapshot increased from **11,853 to 14,014 used
credits**, an observed **2,161 credits**, leaving **42,183 of 56,197**. This
includes the interrupted request; provider snapshots can settle asynchronously.
The ledger remains ignored at `storage/workshop/ales5-20261124/ledger.json`.
No credit purchase, subscription change, push or live deployment is included.
Technical checks do not constitute instructor pronunciation or item review.

## Verification

82 focused tests passed (28 ALES tests plus 54 existing study regressions).
They cover import validation and sense identity, all authored links,
strong/weak/mixed/guessed performance, maximum-length 15-passage tests without repeats, sparse
banks, early stopping, hidden pending results, retries, profile/skill isolation,
review scheduling, persistence/export, audio provenance and decoding. Existing
vocabulary, Lesson 32 and competency-mapping regression tests also pass.
Every new passage is separately scored with mixed answers in both modalities,
checking distinct word evidence, weaker-word priorities and skill isolation.

Browser checks use a disposable local QA profile. They verify reading passage
progression, report grouping, profile counts, a weaker-word review and saved
rating, plus listening playback and withheld transcripts. Screenshot evidence is
stored locally in `storage/exports/ales-study-report.jpg` and is not committed.
The expansion browser check completed two new listening passages (housing and
museum), observed a recording play through, and confirmed six recognized words
plus two missed/guessed words saved to the QA profile. A new weaker word then
opened in review and saved a ten-minute retry schedule. The transcript stayed
hidden until completion. New proof is in
`storage/exports/ales-expansion-preview.jpg`. These technical checks do not
replace a fluent instructor's language/pronunciation review.

The November 23 browser check played the new pool dialogue to completion,
advanced to the new community-event dialogue, and saved six recognized words
and two missed/guessed words in the QA profile. Transcripts appeared only after
completion. The weaker-word review opened successfully, retaining the existing
due-card priority. Proof: `storage/exports/ales-third-batch-report.jpg` (ignored).

The November 24 browser check verified existing passages still update the same
profile evidence, then played the new route-planning dialogue to completion.
It advanced to a second passage and saved six recognized words plus two
missed/guessed words. The new target `стараться` then opened in weaker-word
review and saved a ten-minute retry schedule. Transcripts stayed hidden until
the assessment finished. Proof: `storage/exports/ales-fourth-batch-report.jpg`
(ignored). No real learner profile was used for these checks.

The fifth-batch browser check used a disposable QA profile with seeded prior-bank
history, leaving real learners untouched. It played the new neighborhood-event
recording to completion, advanced to the anniversary dialogue, and saved six
confidently recognized senses and two missed/guessed senses. Transcripts stayed
hidden until completion. The weaker phrase `по крайней мере` opened in listening
review and saved a ten-minute retry. Proof is in ignored
`storage/exports/ales-fifth-batch-report.jpg`. The local preview is signed out and
available at port 7864; the live demo remains unchanged.

The focused regression suite must run with local socket access on Windows:
Gradio's event-loop initialization can stall in a network-restricted sandbox.
The 82-test successful run used local socket access and disabled Gradio analytics.
