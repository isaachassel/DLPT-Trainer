# Adaptive Assessment

Choose **Adaptive Assessment** in Session Setup. Choose Russian or Mandarin Chinese, then Reading, Listening, or both as separate sections. The existing Training, Diagnostic, and Simulation modes remain available.

## Local setup

Use Python 3.11 or 3.12 in a project virtual environment. This implementation was verified on Windows with Python 3.12.14 and the existing pinned dependencies; it adds no runtime packages.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:GRADIO_ANALYTICS_ENABLED = 'False'
$env:GRADIO_SERVER_NAME = '127.0.0.1'
$env:GENERATION_PROVIDER = 'disabled'
$env:AUTO_PROVISION_DATASET_BANK = 'false'
$env:SYNC_GENERATED_BANK_ON_STARTUP = 'false'
$env:SYNC_GENERATED_BANK_ON_WRITE = 'false'
.venv/Scripts/python.exe app.py
```

Open <http://127.0.0.1:7860>. These environment settings affect the current shell and its child processes. No credentials are needed for assessment. All assessment modes now use only curator-approved preset content and fixed local recordings; they do not generate or upgrade audio. Existing starter content remains pending curator review, so the production assessment reports insufficient approved content until review is complete. Training retains its provider and TTS behavior. See the [preset bank and private workshop guide](PRESET_BANK_AND_WORKSHOP.md) for setup and approval. Never commit `.env` or credentials.

Run tests with `.venv/Scripts/python.exe -m pytest -q -rs`. The five existing audio-generation integration tests require ffmpeg (one also requires ffprobe); cached assessment audio does not.

## Model and assumptions

`core/assessment.py` implements a discrete Bayesian passage-testlet model. Reading and listening each start with their own neutral Normal(-0.25, 1.5²) ability prior, evaluated on a -5 to 5 grid in increments of 0.05 and normalized. Prior ability is independent of the selected training starting level and profile history.

For question j in passage t:

```
P(correct_j | theta, delta_t) = c_j + (1 - c_j) * logistic(theta - b_j - delta_t)
c_j = 1 / number_of_choices   # 0.25 for the current four-option schema
b_j = ILR_THETA[question.target_ilr]
delta_t ~ Normal(0, 0.75²)
L_t(theta) = integral product_j P(y_j | theta, delta_t) p(delta_t) d(delta_t)
posterior(theta) proportional to previous_posterior(theta) * L_t(theta)
```

The integral is approximated on offsets -3 to 3 in steps of 0.25 with normalized normal-density weights. Every question is scored, but its passage shares a single latent offset. Marginalizing this offset accounts for within-passage dependence and assumed passage difficulty error. It prevents several questions about one passage from supplying the same information as independent passages. The offset SD is a deliberately fixed modeling assumption, not an estimated correlation or empirically established calibration error. Between-passage independence is still assumed.

The existing ILR-to-theta anchors are 0: -2.50, 0+: -1.75, 1: -1.00, 1+: -0.25, 2: 0.50, 2+: 1.25, 3: 2.00. Their numerical spacing, fixed discrimination of 1, guessing floor, prior, and passage variance are **provisional assumptions**. Assessment ignores any `calibrated_difficulty` or `discrimination` fields rather than treating imported metadata as verified calibration. The shared offset adds uncertainty around authoring labels; it cannot correct systematic mislabeled content or prove ILR validity.

The reported point estimate is the posterior mean mapped to the nearest anchor. The report also gives posterior SD, the central 90% credible interval, its approximate ILR endpoints, and posterior probability within the point estimate's band. Band boundaries are anchor midpoints. The lowest and highest bands pool their respective tails; an interval extending beyond the anchors is explicitly flagged. No level above 3 is inferred. Intervals are conditional on the model and **are not empirical coverage guarantees**.

This follows the general guessing-aware IRT and shared-testlet approach, not any official ODA/DLPT method:

- ETS, [Basic Concepts of Item Response Theory](https://www.ets.org/research/policy_research_reports/publications/report/2020/kbxx.html).
- ETS, [Using a New Statistical Model for Testlets to Score TOEFL](https://www.ets.org/research/policy_research_reports/publications/report/2001/hygp.html), which discusses random effects for questions sharing a stimulus.

Those publications motivate the model family; they do not validate this implementation, its constants, its content, or its ILR mapping. This product neither reproduces the official ODA/DLPT scoring algorithm nor provides a validated official score or test prediction.

## Selection and stopping

The initial passage is nearest the neutral prior mean (normally ILR 1+). After each complete passage, selection uses the accumulated posterior mean and the nearest available provisional question-difficulty mean. Topic/competency preferences and topic balance break ties; passage ID gives reproducible ordering. Unlike the legacy diagnostic, assessment does not require a medium-band passage to exist: sparse banks use the nearest eligible content. There is no assertion of optimal information-based selection.

Only operational passages for the chosen language and skill are eligible, with accepted questions and valid linked listening audio. The configured ILR floor/ceiling applies to all questions in the passage. The full passage is used; question-count limits from other modes do not truncate it. Completed passage IDs, question IDs, and normalized text hashes prevent repeats, including the same passage under a second ID. Optional history first excludes past passages; the existing history fallback can reuse earlier-session material only after that pool runs out, never within the active assessment.

Default limits per skill are **6 minimum / 18 maximum passages**, configurable from 2 to 40 with minimum ≤ maximum. The default uncertainty target is **posterior SD ≤ 0.55**, configurable from 0.30 to 0.80. These are pragmatic practice thresholds, not validated decision cutoffs.

Checks run only after complete passages:

1. Maximum passage count reached: stop, even if precision also happens to be met.
2. Minimum passage count reached, SD meets target, and questions from at least two provisional ILR bands were answered: stop for precision.
3. No eligible unseen content: end that skill explicitly for insufficient content, then continue the other selected skill if available.
4. Learner ends the assessment: report the completed evidence as a partial result.

A point level is withheld below the minimum passage count. At/above the minimum, a point estimate may be shown alongside **inconclusive classification** when precision is unmet, the probability of its band is below 60%, or the assessment was abandoned. Precision stopping and certainty about a single band are different: a sufficiently narrow interval can still straddle a boundary. Restricted difficulty ranges and bank endpoints are called out in the report. Reducing the minimum does not make a short result valid.

The bundled bank contains 12 Russian reading passages (48 questions), 15 Russian listening passages (40 questions), and 12 passages / 36 questions in each Mandarin skill. Thus the default maximum can exceed available content; exhaustion is an expected result and never triggers repetition or a fabricated confident score.

## Session behavior and verification

Answers, explanations, ability estimates, item levels, and listening transcripts stay hidden until **all selected sections have ended**. Answers must be complete and valid before submission. Listening requires browser-confirmed playback and locks replay. Progress, posterior weights, limits, and per-skill end reasons are checkpointed. Resume restores the same shuffled active questions; a checkpoint saved between scoring and selection safely continues selection/stopping without rescoring. Duplicate submission nonces are ignored. Final JSON/CSV exports and full answer/explanation review remain available.

Browser verification found and fixed an existing Gradio 6.5.1 incompatibility: `watch` was not available to the HTML audio script. A scoped `MutationObserver` now binds playback listeners when each new audio node appears; actual browser playback, acknowledgment, and replay locking were checked.

Tests cover strong/weak/mixed/borderline responses, guessing, shared-passage dependence, actual-bank routing, separate skills, whole passages, minimum/maximum/precision stops, zero/one-passage banks, continuation after a missing section, duplicate text, delayed feedback, checkpoint recovery, invalid settings, and both languages and skills. Windows audio-URL test expectations decode URLs before comparing paths; the synthesis-failure unit test mocks the ffmpeg presence check because failure occurs before ffmpeg execution.

Verification on this branch: **264 passed, 5 skipped** (ffmpeg/ffprobe-dependent tests), with `pip check` passing. Browser checks completed two-passage reading and listening assessments, delayed answer/transcript review, exported reports, checkpoint recovery across a server restart, and single-play audio acknowledgment on consecutive passages. Short smoke-test scores were explicitly marked inconclusive. Live provider calls and remote bank synchronization were disabled.
