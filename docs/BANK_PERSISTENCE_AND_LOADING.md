# Loading feedback and generated-bank persistence

## Visible operation feedback

Version 1.2.4 adds a dedicated accessible activity panel for every operation that can take noticeable time:

- Begin Session;
- Resume Session;
- Play or prepare audio;
- Submit Passage;
- Show Strategy Hints;
- Build a partial report;
- Abandon a strict session.

The panel contains an animated spinner, an `aria-live` status message, and an `aria-busy` state. The initiating button changes to a busy label and becomes non-interactive immediately. This prevents uncertainty and duplicate clicks while a queued Gradio callback is running. Session creation, passage selection, adaptive scoring, checkpoint writes, live authoring, bank persistence, and TTS preparation also emit staged `gr.Progress` updates.

## What is saved after fresh generation

A generated bundle is not written to the operational bank until all required stages succeed. The atomic commit contains:

- the complete `PassageItem`;
- every `QuestionItem` with English stem, four English choices, remapped correct key, rationale, Russian evidence, difficulty metadata, validation metadata, and generation metadata;
- passage and question `ValidationReport` records;
- the linked `AudioAsset` for Listening content;
- provider, model, verifier, prompt-version, repair-count, and token metadata when available.

After the atomic JSONL replacement succeeds, the same objects are added to the in-memory indexes immediately. They can therefore be selected as fallback content later in the same session or by another session in the same running Space. The generated bank is loaded together with the starter bank at every application startup.

## Health manifest

Every successful commit refreshes `generated_items.meta.json`. It records:

- SHA-256 checksum;
- total record count;
- passage count;
- question count;
- audio count;
- validation-report count;
- last update time;
- persistence backend;
- remote synchronization state;
- malformed-record warnings.

The setup screen and active-session status display current generated-bank passage and question counts. A malformed generated overlay does not disable the starter bank: bad records are excluded and surfaced as warnings, while only complete, validated bundles are selectable.

## Durability options

### Local Space runtime

With no persistence configuration, accepted items are immediately reusable but can disappear after a Space rebuild or restart because the default filesystem is ephemeral.

### Mounted persistent storage

Set:

```text
PERSISTENT_STORAGE_PATH=/data
```

The generated JSONL bank, manifest, Listening audio, checkpoints, history, exports, and quarantine records are stored under the mounted volume.

### Hugging Face Dataset mirror

Set these Space variables/secrets:

```text
HF_DATASET_REPO=your-username/dlpt-generated-bank
HF_TOKEN=<write-capable token stored as a secret>
STORAGE_BACKEND=hybrid
SYNC_GENERATED_BANK_ON_STARTUP=true
SYNC_GENERATED_BANK_ON_WRITE=true
```

When `HF_DATASET_REPO` is set and `STORAGE_BACKEND` is omitted, the app selects `hybrid` automatically.

At startup, the app downloads and merges the remote generated bank with any newer local records. After every accepted generation, it uploads:

- `generated_items.jsonl`;
- `generated_items.meta.json`;
- generated Listening MP3 files under `audio/`.

On a later restart, remote audio is restored into the controlled audio cache and the JSONL paths are rewritten to the current runtime. If remote synchronization fails, the local atomic commit remains active and the UI reports that the item is usable in the current runtime but not yet durably mirrored.
