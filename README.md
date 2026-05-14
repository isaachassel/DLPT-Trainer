---
title: Russian ILR Trainer
emoji: 📘
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: false
license: mit
---

# Russian ILR Trainer

Adaptive Russian reading and listening practice for serious proficiency test preparation. This is an independent ILR-style study tool and is not official DLPT material.

## Current features

- Reading Practice
- Listening Practice with generated Russian audio
- Full Diagnostic alternating reading/listening blocks
- ILR levels: 0, 0+, 1, 1+, 2, 2+, 3
- Live GenAI generation only; no fallback templates
- End-only feedback
- Scrollable feedback tabs: Summary, Latest Block, All Missed Questions
- Continue Practice button for extra adaptive blocks

## Listening behavior

The app generates a Russian audio script using GenAI, then creates an MP3 voiceover with `edge-tts`. The Russian transcript is hidden during the test. In feedback, the transcript appears for missed listening questions so the learner can review evidence.

The UI recommends listening no more than 2 times to simulate test pressure, but the audio player does not hard-lock playback. For training, users may replay as needed.

## Hugging Face setup

Upload these files at the root of the Space:

```text
app.py
requirements.txt
README.md
LICENSE
.env.example
core/
  __init__.py
  generator.py
  prompts.py
  schema.py
  scoring.py
```

Add this Space secret:

```text
HF_TOKEN=your_huggingface_token_here
```

Recommended optional variables:

```text
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_PROVIDER=auto
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural
```

Optional speed/quality controls:

```text
PASSAGE_MAX_ATTEMPTS=1
QUESTION_MAX_ATTEMPTS=2
ENABLE_PASSAGE_EXPANSION=false
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
# edit .env and add HF_TOKEN
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
