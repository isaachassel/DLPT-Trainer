# Lesson passage competency mappings

Branch: `codex/lesson-study`, created from vocabulary study commit `5469bca`.
This feature is local only. No changes were deployed to the public assessment.

## Practice

Run `study_app.py` and open <http://127.0.0.1:7864/>. Sign in, then expand
**Lesson passages · Four competency categories** near the bottom of the study
workspace. Choose a category and mapped dialogue, then **Practice mapped passage**.
The existing Reading/Listening and module/lesson filters apply. Leave module and
lesson at **All** to explore every category.

| Category | Two-question sets | What is tested |
|---|---:|---|
| Lexical | 17 | Contextual vocabulary meanings |
| Structural | 2 | Motion, task descriptions, completed actions |
| Discourse | 2 | Contrasting accounts, correcting a summary, uncertainty |
| Sociocultural | 2 | Informal address, collaborative suggestions, transaction context |

There are **23 question pairs (46 questions) across 17 existing dialogues**.
Each pair belongs to one explicit category; a dialogue may support several pairs.
All pairs work for reading and listening using the same verified study audio.
No new audio was generated and no ElevenLabs credits were used.

Lesson 32 currently has eight lexical, two structural and two discourse pairs.
The other mappings, including the two sociocultural pairs, explicitly have no
confirmed course lesson. They appear with All module/lesson filters and produce
topic guidance rather than a fabricated lesson recommendation. Sociocultural
questions concern the particular conversation; they do not establish universal
Russian cultural norms or consumer-law rules. All mappings/questions remain
provisional author-created material, not SLS/DLI-reviewed content.

## Results and privacy

Both answers are required; I don't know and guessed answers are supported.
Answers/explanations and listening transcripts stay hidden until submission.
Results lead with Prioritize this lesson (both missed), Review this lesson (one
missed), Review to build confidence (both correct with guessing), or Looking
good so far (both correct confidently). Unmapped content uses “topic” wording.
Guidance names the objective and review reference; it is based on two questions
from one passage, not a mastery claim or DLPT estimate.

`lesson_checks` is an additive SQLite table in the existing private profile
database. Question IDs, selected distractors, guesses, category, lesson mapping,
content revision and time are retained. Active checks snapshot their content;
authoring edits cannot change a check already underway. Duplicate submissions
are idempotent. Ownership is bound to both profile and login, and starting a new
lesson passage cancels unfinished lesson work for that login.

History displays the latest completed attempt for each passage/category/skill.
Repeated attempts remain stored and exported but do not become independent
passages or a proficiency score. Progress export version 3 adds completed lesson
attempts without exporting session tokens or credentials. Existing vocabulary
cards, schedules, checks and assessment histories are preserved. This initial
activity does not modify word-review priorities automatically.

## Authoring

Edit `scripts/prepare_lesson_mappings.py`, then run it to rebuild
`data/study/lesson_mappings.json`. Each mapping includes a stable ID, existing
passage ID, one of `lexical`, `structural`, `discourse`, `sociocultural`, a nullable
lesson ID, objective, review guidance, and exactly two questions. Each question
needs a stable ID, prompt, answer, three distinct distractors, explanation and an
exact supporting excerpt from the dialogue. Changes to mappings do not affect
audio fingerprints because the underlying scripts are unchanged.

The loader rejects missing passages/lessons, unknown categories, duplicate IDs,
incorrect question counts, duplicate choices and evidence absent from the
passage. Course references are explicit, language checked and never inferred
solely from a topic or vocabulary overlap.

## Scope and verification

This is the category-mapping and guided-practice foundation. Automatic lesson
selection/adaptation, aggregate lesson recommendations over time, direct resource
links, instructor analytics and simulation playback rules remain future work.
Listening permits study replays in this initial activity; a two-listen diagnostic
policy is not yet enforced. Existing vocabulary and public assessment behavior
are unchanged.

54 tests passed across lesson mapping, vocabulary study, vocabulary checks and
Lesson 32 content. They cover all four categories, filters/sparse banks, each
recommendation outcome, guessed answers, content snapshots, retries, profile and
skill isolation, repeat deduplication, persistence/export, answer withholding,
invalid mappings, reproducible data and the existing study workflows.

Local browser verification covered lexical reading (one missed), structural
reading (both correct with a guess), and sociocultural listening (both correct).
Verified visible answer choices, audio playback progress, saved skill-specific
history, transcript withholding/reveal, and sign-out clearing the workspace.
Explicit question slots and visibility updates prevent empty Gradio radio forms
when opening the initially hidden practice panel. The 14 lesson tests were run
again after this display fix. Preview proof is saved locally at
`storage/exports/lesson-study-preview.jpg` (not committed).
