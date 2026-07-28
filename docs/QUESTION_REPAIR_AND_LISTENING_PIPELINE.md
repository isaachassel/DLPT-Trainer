# Targeted Question Repair and Listening Pipeline

Version 1.3.3 separates fresh Listening authoring into explicit stages: passage generation, passage audit, question generation, deterministic question checks, blind verification, optional targeted repair, TTS generation, audio validation, and atomic bank persistence.

## Targeted repair

When validation failures identify specific positions such as `q2:no_near_duplicate_choices`, the authoring provider receives only the failed question positions. Valid questions and the accepted Russian passage are preserved. Replacement questions are merged back into their original positions and the entire bundle is revalidated and blind-verified. Whole-set regeneration is reserved for global or unscoped failures.

The default repair limit is two bounded passes. Failed candidates never enter the operational bank.

## Choice similarity

The validator permits parallel grammatical frames when the distinguishing proposition changes materially. It still rejects exact duplicates and options that differ only by a tiny qualifier. Independent blind verification remains the semantic ambiguity gate.

## Evidence normalization

The model must provide short exact Russian evidence. When it supplies a verbose or punctuation-normalized quote, the application may map it to a traceable exact sentence or clause from the passage. The blind verifier must still independently support the keyed answer.

## Audio

TTS begins only after passage and question acceptance. The app logs a sanitized start and success message, validates file size and duration, links the MP3 to the `AudioAsset`, then atomically persists passage, questions, reports, and audio. Failure at any stage preserves the session and selects a validated bank bundle.
