# Skill-Separated Bank Architecture

Version 1.3.4 keeps one durable physical bank while enforcing separate operational Reading and Listening indexes.

## Physical storage

The private Dataset or mounted storage contains one append-only JSONL overlay plus generated Listening audio:

```text
generated_items.jsonl
generated_items.meta.json
audio/*.mp3
```

A single repository simplifies atomic backup, restore, checksums, Dataset synchronization, and version history. It does not mean Reading and Listening records are mixed during selection.

## Logical indexes

At load and after every accepted bundle, `ItemBank._reindex()` rebuilds:

```text
passage_ids_by_skill[reading]
passage_ids_by_skill[listening]
question_ids_by_skill[reading]
question_ids_by_skill[listening]
topics_by_skill[reading]
topics_by_skill[listening]
```

The adaptive selector receives only `active_passages(active_skill)`. Reading performance and selection never use Listening records, and Listening performance and selection never use Reading records.

## Skill/audio contract

### Reading

An operational Reading passage must have:

```text
audio_asset_id = null
audio_duration_seconds = null
voice_metadata = {}
```

Supplying an audio asset with a Reading bundle causes bank admission to fail.

### Listening

An operational Listening passage must reference an `AudioAsset` that:

- exists in the bank;
- has the same ID as `passage.audio_asset_id`;
- is marked validated;
- has a transcript hash matching the Russian transcript;
- resolves to a non-empty audio file.

A restored Listening JSONL record whose MP3 was not restored remains indexed for health reporting but is excluded from operational selection.

## Duplicate policy

- Exact or near duplicate within the same skill: rejected.
- Exact or near equivalent across Reading and Listening: may be stored as an intentional transformation.
- Cross-skill relationships are recorded in provenance metadata.
- Once a learner sees one version, content-hash filtering prevents delivery of the equivalent version in the other skill during the same session or through saved history.

## User-visible health

The setup screen reports Reading and Listening separately. Listening additionally reports generated/operational audio assets and missing-or-invalid audio count. Topic choices update to the selected skill.

The ILR metadata remains provisional until empirical calibration data replaces the provisional difficulty values.
