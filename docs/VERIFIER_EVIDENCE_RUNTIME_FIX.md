# Verifier Evidence Runtime Fix — v1.2.8

## Production symptom

A first Fresh-AI Reading bundle could be accepted, while a later bundle completed every hosted stage and then fell back with:

```text
Generated questions failed validation: q1:verifier_evidence_not_in_passage
```

The provider calls were not failing. Passage authoring, passage audit, question authoring, and blind answer verification all returned successful structured responses.

## Root cause

The application had two evidence fields serving different purposes:

1. `QuestionItem.evidence_ru` — the operational evidence saved with the question, shown during review, and required to be an exact short substring of the passage.
2. `BlindVerification.evidence_quote_ru` — an independent verifier's explanation field.

Both were treated as hard exact-substring gates. Hosted verifier models sometimes preserve the meaning but shorten, normalize, inflect, or paraphrase the supporting text. That behavior caused a valid question to be rejected even when:

- the verifier selected the same answer as the author;
- the verifier marked the evidence sufficient;
- the operational `evidence_ru` was an exact passage quotation;
- all deterministic checks passed.

A question-repair pass could repeat the same failure because the problem was the verifier quote policy, not the authored question.

## Correct behavior

The operational evidence remains strict and exact. Unsupported authored evidence still quarantines the item.

The independent verifier quote is now advisory. Reports store:

- `verifier_evidence_exact` — whether the verifier copied an exact passage substring;
- `verifier_evidence_traceability` — a normalized lexical/fuzzy traceability score.

A non-exact verifier quote does not reject an item by itself. The verifier still rejects the item when it:

- chooses a different answer;
- finds multiple defensible answers;
- requires outside knowledge;
- reports insufficient evidence;
- reports reasoning-level mismatch;
- detects answer leakage;
- returns low confidence under the configured threshold.

## Prompt correction

The verifier prompt now explicitly says to copy an exact contiguous Russian span and not paraphrase it. When no exact span supports the answer, it must return an empty quote and set `evidence_sufficient=false`.

## Bank integrity

This change does not permit unsupported material into the bank. The authored question evidence must still pass the hard deterministic `evidence_in_passage` check before blind verification, after answer shuffling, and before atomic persistence.
