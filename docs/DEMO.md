# Demo branch

`codex/adaptive-demo` starts the demo through the normal `app.py` entry point.
The feature branch keeps the full application. Choose Russian or Chinese, then
Reading or Listening and Begin. There is no combined-test option. It uses the existing approved bank; no generation
credentials, network content generation, new audio purchases or remote bank sync
are required.

Fixed settings: one selected skill, 12 questions, 30 minutes,
neutral medium start, ILR 0–3 routing, submitted passages locked, answer
review at the end. This is deliberately shortened independent practice, not a
replica of the official DLPT algorithm or official listening rules.

Listening: one click starts two unmodified plays of the approved recording, with
a quiet tapered 880 Hz beep between them. The browser unlocks audio on that click.
If autoplay is interrupted, Continue listening resumes the current play. Ordered
browser start/end events are bound to the session and passage; duplicate, stale,
or out-of-order events are ignored. Both plays must finish before submission.
These browser events support a practice workflow, not a tamper-proof proctoring
system. Saved checkpoints remain on disk. A local link with
`?resume=<session-code>` restores a demo checkpoint without adding setup controls.
The original section deadline remains in effect; an expired section is not reset.

Run `.venv/Scripts/python.exe app.py`, then open http://127.0.0.1:7860.
The full interface remains in `ui/layout.py`; the demo is in `ui/demo.py` and its
audio behavior in `ui/demo_audio.js`.

Verification after the playback lifecycle fix: **347 tests passed**, with five
existing FFmpeg-dependent skips. A JavaScript regression executes the actual
audio controller through three replacement HTML hosts. Browser checks confirmed
two consecutive passages each start, play twice, and unlock submission. Playback
and timer bindings resolve the live component after Gradio replaces its inner
host, disposing old listeners rather than retaining detached controls.
Earlier checks also covered Chinese reading-to-listening progression and the
live countdown. For fast manual
audio checks, `scripts/preview_demo_audio.py` serves a temporary local-only
fixture on port 7861 using the shortest existing approved recordings. It does
not change the production demo's selected-skill flow.

Single-skill selection: 29 focused demo/runtime tests passed, including full
Reading-only and Listening-only runs in both languages with strong, weak, and
mixed answers. Each run ends after the selected skill and reports 12 responses.

## Readable demo results

The demo report shows a rough practice location, answer and distinct-passage
counts, a plain-language confidence note, the stopping reason, accuracy by
intended passage level, and a collapsed missed-answer review. The full app's
technical report and the scoring engine are unchanged.

After at least eight submitted questions from at least three passages, the demo
maps the existing posterior mean to the nearest ILR anchor even if the stricter
stable-band rule fails. This is a presentation safeguard, not an empirically
validated minimum. A rounded middle-80% model interval accompanies the location.
No level is shown for sparse evidence or an active test. The interval assumes
the provisional item difficulties are correct; unknown labeling error is not
included. Confidence remains Low when unstable and is capped at Limited even
if the model meets its precision target. Endpoints cannot resolve beyond ILR 0–3.

The 12-question demo is deliberately short. For a substantive pilot, a planning
target is 15–20 reviewed passages at each of seven bands for each language/skill:
105–140 per bank, or 420–560 across Russian/Chinese reading/listening. At 2–3
questions per passage that is 840–1,680 questions. This is a development target,
not a guarantee of score accuracy. Longer sessions (initially exploring 12–20
distinct passages) also need trialing, rather than assuming more bank content
alone fixes precision in a 12-question test.

Before claiming DLPT predictive accuracy, have language/test-development experts
review levels, questions and audio, field-test across proficiency levels, calibrate
item/passages with sufficient responses, and evaluate against recent DLPT scores
on held-out participants. Evaluate errors near each half-level boundary and
test/retest consistency. Translation-assisted attempts are useful workflow checks
but cannot validate unaided language proficiency.

DLI's [published FAQ](https://www.dliflc.edu/resources/dlpt-guides/) describes
multiple reviewers and at least 100, preferably 200 or more, participants taking
a multiple-choice validation form to support calibration. That is context for
the scale of validation, not a universal sample-size prescription for this bank.
ETS discusses why optimal pool size depends on the test in
[Three Practical Issues for Modern Adaptive Testing Item Pools](https://www.ets.org/research/policy_research_reports/publications/report/1994/hxnr.html).

Report redesign verification: 53 focused demo, reporting, and runtime tests passed.
Coverage includes strong/weak/mixed complete runs in both languages and skills,
borderline display mapping, sparse evidence, active-test answer withholding,
HTML escaping, unchanged scoring state, stopping reasons, and timer persistence.
The local browser also verified restoring a completed report and expanding its
missed-answer review. No learner checkpoints are included in test fixtures.

## Hosting preparation

Current audio release: [paid audio refresh, October 6](PAID_AUDIO_REFRESH.md).
All active recordings now have paid-plan generation provenance; the Free-plan
notes below describe the initial deployment only.

`python scripts/package_demo.py` builds an allowlisted ZIP and hash manifest in
`storage/exports/deployment/`. It includes runtime source, schemas, approved bank,
38 recordings, their attribution notice, and a deployment-specific README. It
excludes `.env`, Git history, local results, workshops, tests and bytecode. The
ZIP is a staging artifact: extract its contents at the Space repository root,
or upload the six generated files in `browser-upload/` together. The latter
uses `launch_space.py` to extract the allowlisted archive into a versioned local
directory and run the app, preserving nested file paths through a browser file
chooser. Uploading only the ZIP does not deploy a Gradio app. The packager never
uploads anything. The launcher rejects archive paths outside its destination.

Spaces sets `SPACE_ID`, which automatically enables hosted safeguards. Other
hosts must set `DEMO_HOSTED=true`. Hosted mode disables checkpoint resume URLs
and serves only approved audio, blocking learner storage/export paths, `.env`
and `.git`. Local checkpoint recovery is unchanged. Hosted answers still use
server-side files; no durable retention or account ownership is promised.

Preparation verified 50 focused tests and loaded the clean 89-file package:
66 passages, 156 questions, 38 recordings, no bank warnings. A separate local
hosted-mode server returned 200 for the app and approved audio and 403 for a
synthetic file in the private exports directory. Dependency pins passed the
Space compatibility check. Six hosting/launcher tests passed, and the exact
browser-upload package also launched successfully on localhost.

WordPress page 892 is published at `https://isaachassel.com/language-test/`.
The Language Test item is appended to the existing primary/off-canvas menu.
The page embeds `https://isaachassel-dlpt-adaptive-demo.hf.space` in a responsive
full-width, 1100px-high iframe, with an accessible title, autoplay permission,
and a separate-tab fallback link. It includes educational-use, independent
practice, approximate-score, synthetic-audio, and ElevenLabs attribution copy.
The user explicitly authorized public embedding and publication.

On October 5, 2026, the user authorized the private free-hosting trial. Created
`https://huggingface.co/spaces/isaachassel/dlpt-adaptive-demo` and uploaded the
six-file browser package in Space commit `6705a9bfbb6ee52c53eecdd75515d62f8846334f`.
Archive SHA-256: `c195bdb5dac5cbe49ce821e1fb5dec65198cc288d5c07547616325deb0eaeb19`.
The Linux build completed and Gradio started, but the platform rejected it with
`No @spaces.GPU function detected during startup`. The UI's CPU Basic switch
also failed with an explicit PRO-subscription requirement. No fake GPU workload
was added, no paid hardware was enabled, and no GitHub branch was pushed.
After the user activated Hugging Face PRO, switching the same private Space to
CPU Basic succeeded. The application is running on CPU Basic's free compute;
the user's PRO subscription is separate. No additional paid hardware was enabled.
A browser test completed all 12 Russian reading questions across four passages,
verified progression without showing answers during the test, and displayed
the final readable report (12/12, around ILR 3, low confidence, ILR 2–3 model
range, question-limit stopping reason). This was a software check, not a learner
validation run. WordPress was still a draft at that point.
Hosted Chinese listening was also checked in the browser: the first 70.48-second
recording played twice automatically, submission remained locked until both
plays ended, three answers submitted successfully, and the next distinct
73.2-second recording started normally with submission locked again. This was
a playback/progression check, not a completed listening assessment. Screenshots
are saved locally in `storage/exports/huggingface-reading-report.jpg` and
`storage/exports/huggingface-listening-verified.jpg` (excluded from deployment).

The user clarified this is solely noncommercial educational use and approved
retaining the Free-plan Russian recordings with attribution. Revisit their
license before commercial use; the later Starter subscription does not
retroactively license them commercially. See `data/assessment/audio/NOTICE.md`.
No recordings were regenerated or ElevenLabs credits spent during deployment.

For website publication the Space was changed from Private to Protected: the
app is publicly accessible, while repository source remains private. Both the
published page and app returned HTTP 200 in requests without authentication
cookies. The live page's mobile menu contains the Language Test link, and the
embedded app starts a listening test and plays approved audio successfully.
The embedded Russian recording completed both listens and unlocked submission.
Live-page screenshots are saved under `storage/exports/wordpress-*-live.jpg`
and `storage/exports/wordpress-language-test-published.jpg`.
