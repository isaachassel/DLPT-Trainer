# SLS assessment pilot

Development branch: `codex/sls-assessment-pilot`, based on stable `main`.
This work is not yet published to the live Hugging Face demo or WordPress site.

## Starting difficulty

After choosing Russian or Chinese and Reading or Listening, choose:

- **Preparation · Level 1+** (default).
- **Advanced practice · Level 2**.

Both use the existing 12-question, 30-minute adaptive practice test. Listening
still plays each recording twice with a beep between plays; answers and
explanations remain hidden until the test ends. Either starting point can adapt
up or down. These labels are practice choices, not official DLPT modes.

The chosen band controls the initial passage only. Both choices start with the
same broad ability distribution centered at the existing ILR 1+ anchor. The
choice does not add evidence, improve the initial estimate, or reduce its
uncertainty. The existing guessing correction, passage dependence weighting,
routing thresholds, and report limitations are unchanged.

The first passage must have questions in the selected operational band. If no
approved passage is available there, setup explains the shortage without
creating a checkpoint or an empty report. After answers are submitted, the
normal adaptive range (ILR 0–3) applies, including existing sparse-bank behavior.

`start_level` and `adaptive_start_policy` already exist in session checkpoints;
no schema migration is needed. New demo tests explicitly request a selected
simulation start through `simulation_start_level`. The full application's
simulation default remains Level 2. Older demo checkpoints retain their saved
route, posterior, current passage, audio progress, and deadline on resume.

## Later milestones

Authentic-audio intake, one-question passage routing, FLO topic balancing, and
reviewer analytics remain separate work. No supplied SLS items are added to the
active bank as part of the starting-difficulty change. The existing engine still
requires multiple questions in a passage before changing its routing band.

Publication remains a separate reviewed release after local verification. No
ElevenLabs generation or credits are needed for this change.

## Verification

108 focused tests pass: complete strong, weak, and mixed runs for both starting
levels in both languages and skills; equal initial posteriors and uncertainty;
upward/downward routing; missing starting-band rejection; saved-session and
legacy simulation compatibility; playback guards; reports; and hosting/storage
safeguards. Testing also reproduced a transient Windows checkpoint replacement
failure. Atomic writes now retry Windows access/share locks for at most 350 ms,
then fail with the old checkpoint intact; regressions cover both recovery and
persistent failure.

Local browser verification completed a Russian Reading test from Preparation
through all 12 questions and its report. A Chinese Listening test started from
Advanced practice, played both listens, unlocked submission, and advanced to
the next passage with playback reset. The setup screenshot is saved locally at
`storage/exports/sls-starting-level-setup.jpg` (not deployed).
