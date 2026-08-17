# Blind verifier cardinality recovery — v1.7.9

## Production failure

A Fresh-AI passage could successfully pass authoring, passage audit, question generation, and a hosted `BlindVerificationBatch` request, then be discarded because the returned batch did not contain exactly one object for every zero-based `question_index`.

## Recovery policy

1. Request the normal blind-verification batch with proposed answer keys hidden.
2. If the complete batch is clearly numbered `1..N`, normalize it to `0..N-1`.
3. Keep every unique, in-range batch result.
4. Ignore extraneous out-of-range results.
5. Mark missing or duplicate indexes unresolved.
6. Blindly re-verify only unresolved questions with the single-question schema and an independently shuffled choice order.
7. Merge the recovered reports in original question order.
8. Continue normal deterministic validation and optional secondary verification.

A verifier-cardinality defect therefore cannot by itself destroy an otherwise valid passage. It also cannot bypass verification: every operational question still receives a complete blind verification report.

## Security / assessment integrity

The recovery request does not receive the proposed correct answer. The original Python-side answer mapping and session-side choice shuffling remain unchanged.
