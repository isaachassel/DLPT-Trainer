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

Adaptive Russian reading practice for serious proficiency test preparation. This is an independent DLPT-style, ILR-aligned trainer. It is not official DLPT material and is not affiliated with DLI, DLIFLC, DoD, or any government testing authority.

## Important v1.7 change

This version uses **live GenAI only**.

There are **no fallback/demo/template questions**. If the Hugging Face model call fails, the app shows an error instead of silently giving canned material. This keeps the trainer honest: every passage, question, answer key, explanation, and evidence line must come from the GenAI model.

## Current features

- Russian reading practice
- ILR levels: 0+, 1, 1+, 2, 2+, 3
- Topic domains such as accidents/disasters, government, military/security, economics, public health, and more
- Live GenAI passage generation
- Live GenAI question generation
- Four English multiple-choice comprehension questions per block
- Hidden answer key during the test
- End-only feedback
- Adaptive level movement after each block
- Continue Practice button after the base session length is complete

## Generation pipeline

The app no longer asks one model call to create everything at once. It uses a more reliable two-step pipeline:

1. **Passage call**
   - Generate one Russian passage for the chosen ILR level and topic.
   - Validate length and quality.

2. **Question call**
   - Send that exact passage back to the model.
   - Generate exactly four English comprehension questions.
   - Include A/B/C/D choices, correct answer, explanation, evidence, and question type.

If either step fails after retries, the app stops and displays the error. It does not use fallback content.

## Hugging Face Space setup

Create a new Space:

- SDK: Gradio
- Visibility: Public or Private
- Hardware: CPU basic is okay for the app because generation uses hosted inference

Upload the files so the root of the Space looks like this:

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

Do not upload `__pycache__` folders.

## Required Space secret

Go to:

**Space → Settings → Variables and secrets → New secret**

Add:

```text
Name: HF_TOKEN
Value: hf_your_token_here
```

The token should have this permission:

```text
Inference → Make calls to Inference Providers
```

## Optional Space variables

You may add these under Variables or Secrets:

```text
HF_TEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_PROVIDER=auto
```

Optional token overrides:

```text
HF_PASSAGE_MAX_TOKENS=4200
HF_QUESTION_MAX_TOKENS=2800
```

Usually you do not need to set those manually.

## Recommended first test

Start with:

```text
Mode: Reading Practice
Starting ILR Level: 1+
Target ILR Level: 2
Base Session Length: Short - 8 questions
Topic Domain: Accidents and disasters
```

You should see:

```text
Generation status: Live GenAI generation
```

If generation fails, the app will show an error and the Space logs will contain the exact failed step.

## Troubleshooting

### Error: HF_TOKEN is missing

Add `HF_TOKEN` as a Space secret, not a public variable.

### Error: Generated question set must contain exactly 4 questions

The model returned incomplete JSON. The app retries automatically. If it still fails, try a stronger model or a different provider.

### Error: Generated passage is too short

The model did not follow the ILR length instruction. The app retries automatically. If it still fails, try increasing `HF_PASSAGE_MAX_TOKENS` or using a stronger model.

### Repeated provider/model errors

Try one of these as `HF_TEXT_MODEL`:

```text
Qwen/Qwen2.5-7B-Instruct
Qwen/Qwen2.5-14B-Instruct
Qwen/Qwen2.5-72B-Instruct
meta-llama/Llama-3.1-8B-Instruct
```

Availability depends on your Hugging Face account, provider, and current inference support.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export HF_TOKEN=hf_your_token_here
python app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HF_TOKEN="hf_your_token_here"
python app.py
```

## License

MIT License.
