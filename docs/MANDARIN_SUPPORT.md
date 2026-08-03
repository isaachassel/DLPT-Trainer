# Mandarin Support

Version 1.4.0 added Mandarin as a first-class test language. Version 1.5.0 makes half of the bundled ILR 2+/3 Reading passages Traditional Chinese and alternates Simplified/Traditional instructions for high-level Fresh-AI Reading passages.

## Isolation contract

The learner chooses one language before a session begins. `SessionState.language` is immutable for that checkpoint. Selection filters by both language and skill, so the four logical pools are Russian Reading, Russian Listening, Mandarin Reading, and Mandarin Listening. Passage activation rejects a bundle whose language does not match the active session.

Optional profile history is stored under a language-qualified identity. Russian exposure therefore cannot suppress Mandarin content, and Mandarin responses cannot update a Russian estimate.

## Starter content

`data/mandarin_starter_items.jsonl` contains 12 Reading and 12 Listening passages. Each skill has 36 questions and coverage at ILR 0, 0+, 1, 1+, 2, 2+, and 3. Two of the four ILR 2+/3 Reading passages are Traditional Chinese; lower-level Reading and all hidden Listening transcripts remain Simplified Chinese. All content is original synthetic practice material. Listening records reference bundled `data/audio/zh_l*.mp3` files generated with the Mandarin Xiaoxiao neural voice.

The source schema retains the legacy internal field names `passage_ru` and `evidence_ru` for backward compatibility with existing generated banks. Their values are interpreted according to `PassageItem.language`; the UI and reports call them Mandarin evidence/source text when the language is `zh-CN`.

## Live generation and TTS

The language code is passed to passage authoring, repair, independent audit, question authoring, and blind verification. Mandarin validation uses Han-character ratios and character-based length limits. Normalization tokenizes Han characters so content hashes, evidence matching, and near-duplicate detection remain meaningful without whitespace segmentation.

Generated Mandarin Listening uses `MANDARIN_EDGE_TTS_VOICE` (default `zh-CN-XiaoxiaoNeural`). Training offers Xiaoxiao and Yunxi voice overrides. Russian continues to use the existing Russian voice configuration.

Mandarin Level 3 Listening is synthesized and measured before question authoring. Audio outside 120–150 seconds triggers a bounded transcript repair, while individual sentence limits are measured in Chinese characters rather than whitespace-delimited words.

## Rebuilding the Mandarin bank

The reproducible bank builder is `scripts/build_mandarin_starter_bank.py`. It validates all passage/question/audio relationships before writing the JSONL. Audio files must already exist and pass size/duration inspection; missing audio causes a hard failure rather than silently admitting an unusable Listening item.
