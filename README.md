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


## GenAI provider setup

This app can use Hugging Face first and automatically fall back to Groq when Hugging Face Inference Provider credits/rate limits fail.

Recommended Space secrets:

```text
HF_TOKEN=your_huggingface_token_here
GROQ_API_KEY=your_groq_key_here
```

Recommended variables:

```text
GENAI_PROVIDER=hf_then_groq
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
GROQ_MODEL=llama-3.3-70b-versatile
```

Provider options:

```text
GENAI_PROVIDER=hf_then_groq   # default: try Hugging Face, then Groq
GENAI_PROVIDER=groq           # use Groq only
GENAI_PROVIDER=groq_then_hf   # try Groq, then Hugging Face
GENAI_PROVIDER=huggingface    # use Hugging Face only
```

Do not hard-code API keys in the files. Add them only as Space secrets. If a key is exposed publicly, revoke it and create a new one.

## Listening audio reliability

The listening audio is generated with `edge-tts`. Longer ILR 2+/3 scripts are split into smaller TTS-safe chunks and then joined into one MP3, so the full generated transcript should play instead of cutting off early.

Optional tuning variable:

```text
EDGE_TTS_MAX_CHARS=900
```

Lower this if long audio still cuts off on your host; raise it slightly if audio generation feels too slow.

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


## Listening voice options

The app now includes a UI dropdown for Russian TTS voice and speed. Current voices:

- Russian Female - Svetlana (`ru-RU-SvetlanaNeural`)
- Russian Male - Dmitry (`ru-RU-DmitryNeural`)

The speed dropdown can be left on `Auto by ILR level`, which slows lower levels and uses normal speed for higher levels.

Optional environment overrides still work:

```text
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural
EDGE_TTS_RATE=-5%
```

## v3.1 listening question-quality update

This build adds a final GenAI audit pass for listening questions. The audit is designed to:

- keep explanations in English instead of duplicating the Russian evidence
- keep evidence as a short Russian phrase or clause, not the full transcript
- avoid questions that require math, time subtraction/addition, or unstated inference
- require every correct answer to be explicitly stated or directly supported by the listening script
- show each listening transcript once per missed block in the feedback tabs instead of repeating it under every missed question

Optional environment variable:

```text
ENABLE_LISTENING_QUESTION_AUDIT=true
```

Set it to `false` only if you want faster but less carefully checked listening question generation.

## v3.2 fix

- Fixed listening question audit prompt escaping that could cause `KeyError: '\n  "questions"'`.
- If the optional audit call fails, the app now keeps the original live GenAI-generated question set instead of crashing. No fallback templates are used.
- Listening prompts still instruct the model not to ask math/duration questions unless the answer is directly stated.

## Listening speed controls added in v3.3

The listening question audit improves item quality, but it adds an extra GenAI call. The default is now smart audit mode:

```text
ENABLE_LISTENING_QUESTION_AUDIT=true
LISTENING_AUDIT_MODE=smart
LISTENING_PARALLEL_TTS=true
```

Audit modes:

```text
LISTENING_AUDIT_MODE=smart   # default; audit only risky question sets
LISTENING_AUDIT_MODE=always  # highest quality, slowest
LISTENING_AUDIT_MODE=off     # fastest, uses first generated question set
```

`LISTENING_PARALLEL_TTS=true` generates the MP3 voiceover at the same time as the question generation/audit step, which reduces listening block wait time.

## Upper-level length controls

For ILR 2 and above, the app now performs one expansion pass when a live GenAI reading passage or listening script is shorter than the target. This prevents upper-level content from staying in the 100-word range while avoiding long retry loops.

Optional variables:

```text
ENFORCE_LENGTH_LEVELS=2,2+,3
ENABLE_PASSAGE_EXPANSION=false
ENABLE_LISTENING_EXPANSION=true
HF_PASSAGE_MAX_TOKENS=7600
HF_LISTENING_MAX_TOKENS=7600
```

`max_tokens` is only a ceiling, not a minimum. The app enforces length by counting words and expanding short ILR 2+ outputs once.
