# Hosted Question-Schema Runtime Fix — v1.2.7

## What the production log proved

The provider keys and endpoints were working. Passage authoring succeeded through Hugging Face, and the independent passage audit succeeded through Groq. The failure began only when the application requested `CandidateQuestionSet`. Both providers returned HTTP 200, but every response was rejected locally as a Pydantic `ValidationError`.

Changing provider order, adding output modes, or increasing the stage cap could not solve this because every attempt reused the same incompatible local contract.

## Code defect

The old model used Python validators to require exact question types and ILR labels, but those rules were not represented as JSON-Schema enums. The schema told providers that any string was valid, while the local validator later rejected common values such as `detail`, `central idea`, or `ILR 2`.

It also required the model to return `target_ilr` and `provisional_difficulty` for every question. Those values are internal provisional metadata and should be assigned by application code from the requested session level, question type, and validation results.

## Corrected contract

A provider question now contains exactly:

```json
{
  "stem_en": "English question",
  "choices": ["English A", "English B", "English C", "English D"],
  "proposed_correct_index": 0,
  "rationale_en": "English explanation",
  "evidence_ru": "short exact Russian evidence",
  "question_type": "main idea"
}
```

`question_type` is an actual JSON-Schema enum using the ten supported competencies. Target ILR, difficulty, stable IDs, validation state, and final answer letters are assigned in Python.

## Safe compatibility normalization

The hosted parser can normalize these common variations before strict internal validation:

- a top-level list or `items`, `question_set`, `data`, or `results` wrapper;
- `question`, `stem`, or `prompt` instead of `stem_en`;
- `options` or `answer_choices` instead of `choices`;
- A/B/C/D dictionaries or lists of labeled choice objects;
- `correct_answer: "A"` or a correct answer text instead of a zero-based index;
- `explanation` instead of `rationale_en`;
- `evidence_quote_ru` instead of `evidence_ru`;
- safe synonyms such as `detail`, `central idea`, `author intent`, or `tone`;
- extra model metadata, which is discarded rather than persisted.

This compatibility layer does not admit an item directly into the bank. Every normalized question still passes deterministic validation, blind verification, answer shuffling/remapping, passage-level validation, duplicate detection, and atomic persistence.

## Failure diagnostics

A remaining failure now reports exact locations, for example:

```text
questions.0.choices: Field required;
questions.0.proposed_correct_index: Field required
```

The diagnostic omits generated content and secrets. Failed content remains outside the operational bank.

## Verification

- 93 automated tests passed.
- The provider-facing schema was inspected to verify the enum and six-field contract.
- A realistic hosted payload using `items`, an A/B/C/D dictionary, `correct_answer: "A"`, `type: "detail"`, extra ILR/difficulty fields, and extra metadata was accepted on the first provider attempt.
- A complete generation service flow normalized such a payload, assigned the requested ILR and difficulty in Python, validated the questions, atomically saved the bundle, and immediately indexed it in the reusable bank.
- Starter-bank, Space dependency, Gradio smoke, and HTTP launch checks passed.

A real external call was not made during release packaging because Space secret values are not available outside the user's deployment. The correction directly targets the local validation boundary demonstrated by the production log.
