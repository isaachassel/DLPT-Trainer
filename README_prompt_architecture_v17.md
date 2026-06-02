# ILR Trainer v17 — Prompt Architecture Fix

This update fixes the real issue: the GenAI prompt was asking for length and segments, but it was not guiding the model strongly enough on how to build a listenable passage.

## Main change

Listening generation now uses an information-arc prompt for every level:

- ILR 0: one recognition moment
- ILR 0+: immediate-needs phrases
- ILR 1: simple routine situation
- ILR 1+: situation + response/change
- ILR 2: factual situation + result/next step
- ILR 2+: situation + complication/attitude + consequence
- ILR 3: event + stakeholder response + complication/tradeoff + implication/outlook

## Why this matters

The old prompt could produce long scripts by repeating generic lines.  
The new prompt tells the model that word count must come from new information, not padding.

## Key anti-loop rules added

- Do not repeat any full sentence.
- Do not reuse the same 7+ word phrase across segments.
- Do not repeat generic status lines across segments.
- Every segment must add at least one new fact.
- If the passage is short, expand by adding timeline, stakeholder, consequence, uncertainty, contrast, or next step.

## Question prompt improvements

The question prompt now guides all levels, not only ILR 3:

- 0/0+: recognition only
- 1/1+: concrete simple comprehension
- 2: factual comprehension
- 2+: supported implication / attitude / important vs secondary detail
- 3: mostly cross-segment comprehension, max one simple detail question

## Files changed

- `core/prompts.py`

The v16 deterministic quality gates are kept as backup safety checks, but the main fix is now the prompt itself.
