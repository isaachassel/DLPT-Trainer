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

## Disclaimer

This is an independent Russian ILR-style study tool. It is not official DLPT material and is not affiliated with DLI, DLIFLC, DoD, or any government testing authority. The estimated level is for practice guidance only.

## Current version

Version 1.4 focuses on Reading Practice. Listening Practice and Full Diagnostic are reserved for the next build.

This version includes:

- Russian reading passages by ILR level: 0+, 1, 1+, 2, 2+, 3
- Four English multiple-choice comprehension questions per block
- Hidden answer key until final review
- End-only missed-question explanations
- Adaptive movement between ILR bands
- Visible generation status: Live AI generation or Demo fallback mode
- Larger generation token budgets for longer ILR 2 / 2+ / 3 passages
- Safer fallback so the app does not crash if model generation fails

## Hugging Face Space setup

Create a new Hugging Face Space:

1. Go to Hugging Face Spaces.
2. Create a new Space.
3. Select Gradio as the SDK.
4. Upload the contents of this folder to the root of the Space.

The Space root should look like this:

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

Do not upload the outer folder itself. Upload the files inside it.

## Required Space secret

The app needs a Hugging Face access token for live AI generation.

In your Space, go to:

```text
Settings -> Variables and secrets -> New secret
```

Add:

```text
Name: HF_TOKEN
Value: hf_your_token_here
```

Make sure this is added as a secret, not a public variable.

## Creating the Hugging Face token

Recommended token settings:

```text
Token type: Fine-grained
Token name: DLPT-Trainer
User permissions:
  Inference:
    Make calls to Inference Providers
```

You do not need write access to repositories, billing access, webhooks, jobs, or organization permissions.

## Optional Space variables

You can also add these if needed:

```text
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_PROVIDER=auto
```

For debugging only, you can override the output token budget:

```text
HF_MAX_TOKENS=4200
```

Normally, leave `HF_MAX_TOKENS` unset because the app chooses token budgets by ILR level.

## How to know if live generation is working

Each block shows one of these lines:

```text
Generation status: Live AI generation
```

or:

```text
Generation status: Demo fallback mode
```

If you see Demo fallback mode, the app is running, but the model call failed or `HF_TOKEN` is missing. The app will show a short fallback reason in the progress area and more detail in the Space logs.

Common causes:

- Missing `HF_TOKEN`
- Token added as a public variable instead of a secret
- Token does not have Inference Provider permission
- Model/provider temporarily unavailable
- Model returned invalid JSON
- Model output was too short for the requested ILR level

## Local setup

### Mac / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your HF_TOKEN
python app.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and add your HF_TOKEN
python app.py
```

Then open the local Gradio URL shown in the terminal.

## License

MIT License. See `LICENSE`.
