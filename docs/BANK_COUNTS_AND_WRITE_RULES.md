# Bank counts and write rules

## Sources

The application uses one operational pool assembled from two sources:

1. **Built-in validated starter bank** — immutable repository content.
2. **Saved AI-generated bank** — accepted Fresh-AI bundles and explicit imports stored in the writable overlay and private Dataset.

A bank-only session selects from these sources but does not copy, append, or re-save the selected passage. Opening, answering, replaying, or checkpointing an existing item does not mutate the generated-item JSONL.

## Ready to use

“Ready to use now” is not a third bank. It is the validated subset of starter plus saved AI-generated content that can currently be selected. Listening content is ready only when its linked audio exists, is non-empty, is validated, and matches the transcript hash.

## Allowed writes

The saved AI-generated bank changes only after:

- an accepted Fresh-AI generation passes all gates and commits atomically; or
- a user explicitly imports and merges a backup.

Normal session selection and response logging never add content records.

## Startup snapshot

The startup restore message reports the bank size at launch. Current totals may later be higher when accepted Fresh-AI bundles are added after startup. The UI labels these separately to avoid suggesting that a bank-only selection created content.
