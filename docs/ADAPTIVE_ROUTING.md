# Adaptive Routing Design

## Purpose

The application uses a continuous Bayesian Rasch/1PL estimate for each skill and a separate conservative ILR delivery band for passage routing. Reading and Listening never share ability, routing, uncertainty, evidence counts, or history.

The delivery band is not the score. It is the level of the next passage bundle the selector should prefer.

## Publicly documented behavior approximated

The public DLPT5-CA familiarization description says Reading and Listening begin with a medium-difficulty passage, then select the next passage and questions based on the examinee's answers. This application approximates that behavior without claiming to reproduce the official algorithm.

## Ability update

For every answered question:

```text
P(correct) = 1 / (1 + exp(-(theta - b)))
```

The posterior is updated over a fixed theta grid. The application records:

- EAP posterior mean;
- posterior standard error;
- 80% posterior interval;
- predicted success at each ILR reference point;
- evidence and correct counts by ILR band.

Initial item difficulties are provisional. Empirically calibrated difficulty replaces provisional difficulty when available.

## Passage routing

The routing band uses the Bayesian posterior rather than raw score thresholds.

After each completed passage:

1. Compute posterior probability below the boundary between the current band and the adjacent lower band.
2. Compute posterior probability above the boundary between the current band and the adjacent higher band.
3. Move down one half-level when lower-boundary probability reaches 67% and is stronger than the upward probability.
4. Move up one half-level when upper-boundary probability reaches 67%.
5. Otherwise remain at the current band.
6. Never move more than one adjacent half-level after a passage.
7. Never move outside the configured ILR floor and ceiling.

Example:

```text
Start ILR 3
Three supported ILR 3 questions answered incorrectly
Next routing band: ILR 2+
Continued weak evidence at ILR 2+
Next routing band: ILR 2
```

A single incorrect response normally does not force a large drop. This reduces unstable oscillation and avoids treating one response as conclusive.

## Item selection

The bank selector first enforces hard eligibility:

- correct skill;
- accepted and active validation status;
- unseen passage and questions;
- allowed topic constraints;
- configured ILR floor/ceiling;
- complete valid Listening audio where required.

It then prefers the current routing band. If no unseen accepted passage exists at that band, it uses the nearest adjacent eligible band rather than jumping across multiple levels.

Within the eligible band, it scores candidate passages using:

- Fisher information near the current posterior mean;
- distance from estimated ability;
- routing-band distance;
- Training target-level bias;
- topic balance;
- genre balance;
- question-type balance;
- passage and item exposure;
- calibrated-item preference.

Near-equivalent top candidates are selected with deterministic session-seeded randomization to reduce systematic item overexposure while preserving checkpoint reproducibility.

## Diagnostic boundary probes and stopping

An Adaptive Diagnostic does not stop only because standard error is small. It also requires evidence in the current routing band and at least one adjacent band.

When adjacent evidence is thin, the selector deliberately probes the closest under-sampled adjacent band. This improves floor/ceiling classification and prevents a stable estimate from being based entirely on one nominal band.

The diagnostic stops when:

- the configured maximum is reached; or
- the minimum question count is met;
- posterior standard error is at most 0.45; and
- current/adjacent-band evidence requirements are met.

## Mode behavior

### Training

- Prior and routing begin at the selected starting band.
- User-selected minimum and maximum ILR bands are hard constraints.
- The target band biases selection inside the allowed range.
- Current routing band is visible after answers are locked and in status text.

### Adaptive Diagnostic

- Default start is medium difficulty.
- Optional selected-band start is available as a targeted challenge.
- User-selected minimum and maximum bands are hard constraints.
- Current route is hidden during testing and disclosed in the final report.
- Range-limited diagnostics are labeled as such and are not presented as full-spectrum estimates.

### Full CA Simulation

- Begins at medium difficulty.
- Uses the full supported 0–3 range.
- Current routing and exact ability calculations remain hidden during the active test.
- Final report includes the routing path after completion.

## Important limitation

The starter and generated-bank ILR values are authoring/validation targets until sufficient response data support empirical calibration. The application therefore reports provisional practice estimates, not official DLPT scores or official item classifications.
