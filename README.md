---
title: Russian ILR Trainer
emoji: 📘
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: false
license: mit
---

# Russian ILR Trainer

Adaptive Russian reading practice for serious proficiency test preparation.

This is **DLPT-style, ILR-aligned practice**. It is not an official DLPT product and is not affiliated with DLI, DLIFLC, DoD, or the testing program.

## Current build

Version 1 proves the adaptive reading engine:

- Russian-only MVP
- Reading Practice mode
- ILR levels 0+, 1, 1+, 2, 2+, 3
- AI-generated Russian passages
- English multiple-choice comprehension questions
- End-only review
- Missed-question explanations
- Adaptive level movement
- Final estimated reading level

Listening Practice and Full Diagnostic are included in the UI as reserved Version 2 modes.

## Files

```text
app.py
requirements.txt
.env.example
core/
  generator.py
  prompts.py
  scoring.py
  schema.py
```

## Hugging Face setup

1. Create a new Hugging Face Space.
2. Choose **Gradio** as the Space SDK.
3. Upload all files from this folder.
4. Add your token as a Space secret:

```text
HF_TOKEN=your_huggingface_token_here
```

5. Optional model settings:

```text
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_FAST_MODEL=Qwen/Qwen2.5-3B-Instruct
```

If no token is set, the app still runs with a built-in demo passage so you can test the UI.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

## Next build

Version 2 should add:

- Listening Practice
- Russian TTS audio
- 2-play limit
- transcript hidden during test
- transcript shown only for missed listening questions
- Full Diagnostic mode with separate Reading and Listening estimates
