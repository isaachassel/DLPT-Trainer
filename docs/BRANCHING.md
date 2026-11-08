# Branch and release policy

As of November 7, 2026, `main` is this project's stable application branch.
It includes the completed adaptive-assessment and demo work. It is no longer
an untouched mirror of the original Hugging Face project. The `upstream`
remote remains available for deliberate review of upstream changes.

## Active development

- `main`: stable assessment demo; `app.py` remains its entry point.
- `codex/russian-vocabulary-study`: separate local vocabulary studio and
  unfinished study development. Its `study_app.py` is not the public demo.
- Start new features from current `main` using a descriptive `codex/` branch.
  Review and test before merging. Bring stable maintenance into longer-lived
  feature branches without merging unfinished features into `main`.

GitHub pushes do not deploy the application. Hugging Face publication uses an
explicit reviewed deployment package. WordPress embeds the existing Space.
Branch cleanup does not change either live service. Keep deployment approval
separate from permission to commit, merge, or push source changes.

## Preserved milestones

| Tag | Preserved revision |
| --- | --- |
| `archive/upstream-baseline-20261107` | `b9b1c52`, original upstream-aligned main |
| `archive/adaptive-assessment-20261107` | `b79ab9b`, completed assessment branch |
| `archive/isaac-dev-20261107` | `fb78f33`, original development merge history |
| `release/demo-20261017` | `71886c0`, source baseline documented for the live demo |
| `archive/vocabulary-study-20261107` | `1159405`, study branch including the question-slot fix |

`codex/adaptive-assessment`, `codex/adaptive-demo`, and `isaac-dev` can be
retired after these tags and the consolidated branches are verified on GitHub.
The merge commit unique to `isaac-dev` adds no unique application code but is
retained by its archive tag. No published history is rewritten.

## Local data and backups

Python bytecode, runtime audio caches, generated-bank overlays, and learner
sessions are not source files. Their previously tracked copies are removed
from the current index; ignore rules prevent routine staging of new copies.
Historical commits and archive tags still contain old tracked versions.

Keep `.env`, local profiles, imported course vocabulary, learner progress,
workshops, and exports out of Git and public deployment packages. Back them up
separately. Snapshot a running SQLite database through its backup API rather
than copying only the database file while writes may be pending.

Before consolidation, local backups were verified under
`storage/exports/branch-cleanup-20261107/`: a complete Git bundle, local LFS
objects, a checksummed local-data archive with a consistent profile snapshot,
and the uncommitted patch. This ignored directory is local, not a GitHub or
off-machine backup. Keep a private off-machine copy for device-loss recovery.
Never upload this directory to a public repository or Space.

Git bundles contain Git objects, not the actual large files stored in LFS.
Preserve LFS separately and verify that release audio can be fetched from the
remote before removing its development branch. Release packaging validates
active audio checksums and licensing metadata.
