# Contributor export kit

Preferred delivery: one ZIP containing UTF-8 JSON and optional original files.
Use `contributor.schema.json` as the contract and `contributor.example.json` as
three working examples (Russian reading, Mandarin reading, Russian listening).
The examples are fictional project material, not authentic DLI test items.
Give Claude Code this entire folder and the prompt in `CLAUDE_PROMPT.md`.

## Folder layout

```text
language-materials/
  contributor.json       # Structured, question-ready passages
  manifest.csv           # Inventory: ID, source file, page/time, skill, readiness
  pending.md             # Missing answers, uncertain OCR, unclear rights/levels
  sources/               # Originals when sharing them is authorized
  audio/                 # Optional original MP3, WAV or M4A recordings
```

Keep originals unchanged. Passages without ready questions belong in `sources/`
and the inventory, not JSON items with invented answers. Do not invent evidence,
rights or proficiency labels to satisfy the schema. Split batches above 500 items.

## Per passage

- `id`: unique stable identifier, 1–80 letters, numbers, underscores or hyphens.
- `language`: `ru` or `zh-CN`. Mandarin uses the Simplified Chinese profile.
  Preserve Traditional originals separately and flag for review; do not silently
  convert script.
- `skill`: `reading` or `listening`. Listening needs a faithful transcript even
  when audio is supplied.
- `target_ilr`: string `0`, `0+`, `1`, `1+`, `2`, `2+`, or `3`.
  Include `difficulty_rationale` and who supplied/estimated the label.
  It remains provisional, never calibrated or an official score.
- `genre`, `topic`, `orientation_en`: English context without answer clues.
- `text`: complete target-language passage/transcript, preserving punctuation
  and paragraphs using JSON `\n\n`. No translation, HTML, Markdown headings,
  phonetic rendering or automatic simplification. Preserve transcript speaker
  labels. Record excerpt boundaries in the source locator.
- `source_type`: `authentic/open-licensed` for authentic material,
  `transformed/adapted` for edited material, `synthetic` for invented text.
  This legacy category name does **not** establish a license; rights are separate.
- `source`: title, creator, locator (URL or filename with pages/time range), date,
  exact known rights/permission, attribution requirements, and modifications.
  Use `Unknown` for missing facts. Public access alone does not establish reuse
  rights on a public website.
- `audio_file`: `null`, or a relative path such as `audio/ru_news_001.mp3`.
  Original audio is preferred when available and shareable. Preserve it unchanged
  and identify exact start/end times in `source.locator`. No ElevenLabs needed.
- `notes`: OCR issues, dialect/register, question concerns and reviewer comments.

Export only material authorized for sharing and this project. Exclude restricted
test items, credentials, learner records and private personal data. If permission
to share is unclear, supply a citation for review instead of source contents.

## Per question

Reading supports **1–5** questions per passage; listening **1–3**. Two or three
well-supported questions are useful. Keep questions with their passage.

- `stem_en`: English question.
- `choices`: four distinct strings keyed `A`, `B`, `C`, `D`.
- `correct_key`: exactly one of those letters.
- `rationale_en`: English explanation of the answer and, when available, why
  distractors are wrong.
- `evidence`: short exact source-language excerpt from `text`. For inference
  questions explain the reasoning in the rationale as well.
- `question_type`: `main idea`, `prominent detail`, `inference`,
  `speaker/writer intent`, `tone or attitude`, `reference`, `sequence`,
  `cause and effect`, `relationship of ideas`, or `meaning from context`.
- `origin`: `copied`, `adapted`, `human-authored`, or `AI-authored`. Put separate
  question-source citations in `notes` when needed.

Preserve choice order and answer keys. Do not force key balance; the app shuffles
answer positions. Flag ambiguous items rather than silently repairing them.

Current review checks flag Russian text above 500 words (reading) / 390 words
(listening), and Mandarin above 1,000 / 750 target-language counting units.
Keep full originals regardless; document excerpt boundaries and review any cuts.
Length alone does not determine ILR.

## Project-side import

Extract a trusted contributor ZIP to a local review folder. From the repository:

```powershell
.venv/Scripts/python.exe scripts/import_contributor.py path/to/contributor.json --output storage/workshop/contributor-batch-001
```

This writes `package.json`, normalized `contributor.json`, and `intake-report.json`
in a **new** workshop folder. It refuses existing folders and destinations outside
the workshop. It never changes the active bank, publishes, generates audio or
spends credits. Schema errors stop conversion; semantic concerns are reported
without rewriting source text or answers.

Everything remains `draft`, with `needs_review` validation status. Review source
rights, language, questions, evidence and provisional levels. After corrections,
the curator sets passage/question validation statuses to `accepted`, runs
`scripts/curate_assessment.py validate --package <workshop>/package.json`, and
explicitly approves items with reviewer, notes and reuse attestation. Structural
checks do not confer approval. The contributor need not calculate hashes or
scoring parameters or use legacy internal `passage_ru` / `evidence_ru` fields;
the importer maps `text` / `evidence` for both languages.

Audio paths remain candidate metadata only. Listening drafts require separate
recording ingestion, transcript/checksum/duration verification and rights review.
The current demo packaging gate supports reviewed paid-TTS provenance; authentic
recordings require an explicit extension after reviewing their actual license
and attribution requirements. Never invent ElevenLabs provenance for them.
