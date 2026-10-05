# Demo branch

`codex/adaptive-demo` starts the demo through the normal `app.py` entry point.
The feature branch keeps the full application. This demo offers only Russian or
Chinese and a Begin button. It uses the existing approved bank; no generation
credentials, network content generation, new audio purchases or remote bank sync
are required.

Fixed settings: Reading then Listening, 12 questions per section, 30 minutes per
section, neutral medium start, ILR 0–3 routing, submitted passages locked, answer
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
not change the production demo's Reading-then-Listening flow.
