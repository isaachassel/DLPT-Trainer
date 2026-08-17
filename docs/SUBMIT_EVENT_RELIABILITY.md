# Submit Passage event reliability — v1.8.0

## Production symptom

A generated Reading bundle completed successfully and was persisted, but pressing **Submit Passage** produced no subsequent application log entry and no visible progression. Because no Python callback entry appeared, the failure was upstream of scoring/adaptive logic.

## Root cause

The UI wired Submit as two events:

1. a `queue=False` click handler that changed the same button to **Submitting…** and disabled it; then
2. a chained `.then(...)` event that invoked the real submission callback.

This split browser event chain is more fragile than a single queued assessment action. If the chain stops after stage one, the button is disabled and the real server callback is never invoked, which exactly explains a silent Space log.

## Repair

`submit_passage_stream_callback` is now the only Submit click target. It is a queued generator callback. Its first yield changes only the activity/status display and the Submit button. Every assessment value uses `gr.skip()`, so the active state, bundle, nonce, passage, and selected answers remain untouched. The same callback then calls the existing scoring/submission logic and yields the final render.

The callback logs `Submit passage event received` before scoring and `Submit passage event completed` after the normal callback returns. Unexpected wrapper-level exceptions are logged with a traceback and recover to the same passage with the learner's radio selections restored.

## Regression coverage

Tests assert that the old `submit_prepare.then` chain cannot be reintroduced, that the first generator yield contains exactly the activity plus normal render outputs, that it disables Submit without altering assessment state, and that entry logging occurs before scoring.
