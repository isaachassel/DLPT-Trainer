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

Adaptive Russian reading practice for serious proficiency test preparation. This is DLPT-style, ILR-aligned practice, not an official DLPT product.

## Current version

Version 1.1 includes:

- Reading Practice
- AI-generated Russian passages
- English multiple-choice comprehension questions
- Hidden answer key until the end
- Adaptive ILR level movement between blocks
- Visible adaptive status after each submitted block
- Longer level-appropriate passages for ILR 2, 2+, and 3
- Final report with missed questions, evidence, explanation, weak areas, and adaptive path

Listening Practice and Full Diagnostic are reserved for Version 2.

## Hugging Face setup

Create a Gradio Space and upload the files so the Space root contains:

```text
app.py
requirements.txt
README.md
LICENSE
.env.example
core/
```

Add this Space secret:

```text
HF_TOKEN=your_huggingface_token_here
```

Optional:

```text
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_FAST_MODEL=Qwen/Qwen2.5-3B-Instruct
```

Restart the Space after adding secrets.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add HF_TOKEN to .env
python app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

## Disclaimer

This is an independent Russian ILR-style study tool. It is not official DLPT material and is not affiliated with DLI, DLIFLC, DoD, or any government testing authority. The estimated level is for practice guidance only.
