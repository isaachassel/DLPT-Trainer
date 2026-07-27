# Durable generated-item bank

## Why the bank previously reset

Hugging Face Spaces runs application code inside a replaceable container. Files created under the normal project path are available only for that container lifetime. A restart or rebuild can therefore replace `storage/item_bank/generated_items.jsonl` with a fresh runtime filesystem.

## v1.3 behavior

The application now protects accepted generated content in three ways:

1. **Automatic private Dataset persistence**
   - On a Hugging Face Space, the app derives a private Dataset repository from `SPACE_ID` or `SPACE_HOST`.
   - `HF_BANK_TOKEN` is preferred for repository writes; `HF_TOKEN` is a backwards-compatible fallback.
   - The Dataset is created when needed.
   - The JSONL bank, health manifest, and generated Listening MP3 files are uploaded after each accepted bundle.
   - The remote bank is restored and merged before the operational `ItemBank` loads at startup.

2. **Mounted storage support**
   - `PERSISTENT_STORAGE_PATH=/data` keeps the bank and audio on a mounted volume.

3. **Portable manual backup**
   - **Download Generated Bank Backup** creates a ZIP containing:
     - `generated_items.jsonl`
     - `generated_items.meta.json`
     - generated Listening audio under `audio/`
     - `backup_info.json`
   - **Import and Merge Backup** merges records by stable ID and restores audio into the active cache.
   - Existing records win on duplicate IDs, while unique imported records are added.

## Required Space secret

Recommended:

```text
HF_BANK_TOKEN=<Hugging Face token with repository write permission>
```

The app may reuse `HF_TOKEN` when it already has write permission, but a separate bank token is safer and easier to rotate.

## Optional variables

```text
AUTO_PROVISION_DATASET_BANK=true
AUTO_DATASET_REPO_SUFFIX=dlpt-generated-bank
SYNC_GENERATED_BANK_ON_STARTUP=true
SYNC_GENERATED_BANK_ON_WRITE=true
HF_DATASET_PRIVATE=true
```

To force a specific Dataset repository:

```text
HF_DATASET_REPO=alsubij/dlpt-trainer-generated-bank
STORAGE_BACKEND=hybrid
```

## Status meanings

- `restart-safe private HF Dataset`: writes are mirrored and the last synchronization succeeded.
- `restart-safe mounted persistent storage`: local paths use a mounted volume.
- `private HF Dataset configured but last sync failed`: local items remain usable during this runtime, but download a backup before restart.
- `NOT restart-safe — ephemeral local Space storage`: the bank will reset when the container is replaced.

## Release safety

Release ZIP files no longer include empty `generated_items.jsonl` or `generated_items.meta.json` files. The app creates runtime files only when absent. This prevents a source-folder copy from replacing a checked-in bank with a packaged blank file.
