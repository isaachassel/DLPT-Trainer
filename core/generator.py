from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .prompts import (
    GENERATION_SYSTEM_PROMPT,
    PASSAGE_GENERATION_PROMPT,
    QUESTION_GENERATION_PROMPT,
    PASSAGE_LENGTH_GUIDE,
)
from .schema import Question, TestBlock

load_dotenv()

# Soft target Russian word counts by ILR level. These are quality targets, not hard gates.
# The app should never fall back to templates just because the model wrote a shorter passage.
TARGET_WORDS_BY_LEVEL = {"0+": 70, "1": 110, "1+": 150, "2": 230, "2+": 320, "3": 430}

# Absolute floor to prevent unusably tiny outputs. Anything above this is accepted as live GenAI.
# Short live passages are allowed; they are flagged in the UI instead of rejected.
ABSOLUTE_MIN_WORDS_BY_LEVEL = {"0+": 35, "1": 45, "1+": 55, "2": 70, "2+": 90, "3": 120}

# Output budgets. The pipeline splits generation into passage first, then questions,
# so each call has a clearer job and less chance of returning incomplete JSON.
PASSAGE_TOKENS_BY_LEVEL = {
    "0+": 1200,
    "1": 1700,
    "1+": 2300,
    "2": 3600,
    "2+": 4800,
    "3": 6500,
}
QUESTION_TOKENS_BY_LEVEL = {
    "0+": 1800,
    "1": 2000,
    "1+": 2400,
    "2": 2800,
    "2+": 3200,
    "3": 3600,
}

class GenerationFailure(RuntimeError):
    """Raised when live GenAI generation fails. There is intentionally no template fallback."""


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return a complete JSON object.")
    return json.loads(text[start : end + 1])


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _has_bad_repetition(text: str) -> bool:
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if p.strip()]
    if len(parts) < 2:
        return False
    return any(parts[i] == parts[i - 1] for i in range(1, len(parts)))


def _validate_passage(data: Dict[str, Any], level: str, topic: str) -> Dict[str, Any]:
    title = str(data.get("passage_title", "")).strip()
    passage_ru = str(data.get("passage_ru", "")).strip()
    if not title:
        raise ValueError("Generated passage_title is empty.")
    if not passage_ru:
        raise ValueError("Generated passage_ru is empty.")
    words = _word_count(passage_ru)
    target_words = TARGET_WORDS_BY_LEVEL.get(level, 150)
    absolute_min = ABSOLUTE_MIN_WORDS_BY_LEVEL.get(level, 55)
    if words < absolute_min:
        raise ValueError(f"Generated passage is unusably short for ILR {level}: {words} words, expected at least {absolute_min}.")
    if _has_bad_repetition(passage_ru):
        raise ValueError("Generated passage contains repeated consecutive sentences.")

    length_note = ""
    if words < target_words:
        length_note = (
            f"Live GenAI passage accepted, but it is shorter than the ILR {level} target "
            f"({words} words; target is about {target_words}+)."
        )

    return {
        "skill": "reading",
        "ilr_level": str(data.get("ilr_level", level)).strip() or level,
        "topic": str(data.get("topic", topic)).strip() or topic,
        "passage_title": title,
        "passage_ru": passage_ru,
        "length_note": length_note,
        "word_count": words,
    }


def _validate_questions(data: Dict[str, Any]) -> List[Question]:
    raw_questions = data.get("questions", [])
    if not isinstance(raw_questions, list):
        raise ValueError("questions must be a list.")
    if len(raw_questions) != 4:
        raise ValueError(f"Generated question set must contain exactly 4 questions, got {len(raw_questions)}.")

    questions: List[Question] = []
    for i, q in enumerate(raw_questions, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"Question {i} is not an object.")
        choices = q.get("choices", {})
        if not isinstance(choices, dict) or not all(k in choices for k in ["A", "B", "C", "D"]):
            raise ValueError(f"Question {i} choices must include A, B, C, D.")
        correct = str(q.get("correct_answer", "")).strip().upper()
        if correct not in ["A", "B", "C", "D"]:
            raise ValueError(f"Question {i} correct_answer must be A, B, C, or D.")
        question_text = str(q.get("question", "")).strip()
        if not question_text:
            raise ValueError(f"Question {i} text is empty.")
        if not str(q.get("explanation", "")).strip():
            raise ValueError(f"Question {i} explanation is empty.")
        if not str(q.get("evidence", "")).strip():
            raise ValueError(f"Question {i} evidence is empty.")
        questions.append(
            Question(
                id=str(q.get("id", f"Q{i}")) or f"Q{i}",
                question=question_text,
                choices={key: str(choices[key]).strip() for key in ["A", "B", "C", "D"]},
                correct_answer=correct,
                explanation=str(q.get("explanation", "")).strip(),
                evidence=str(q.get("evidence", "")).strip(),
                question_type=str(q.get("question_type", "comprehension")).strip() or "comprehension",
            )
        )
    return questions


def _make_client(token: str) -> InferenceClient:
    provider = os.getenv("HF_PROVIDER", "auto").strip() or "auto"
    try:
        return InferenceClient(provider=provider, token=token)
    except TypeError:
        return InferenceClient(token=token)


def _call_hf_chat(client: InferenceClient, model: str, messages: List[Dict[str, str]], max_tokens: int):
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.55,
            top_p=0.9,
        )
    except TypeError as first_error:
        try:
            legacy_client = InferenceClient(model=model, token=os.getenv("HF_TOKEN"))
            return legacy_client.chat.completions.create(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.55,
                top_p=0.9,
            )
        except Exception:
            raise first_error


def _generate_passage(client: InferenceClient, model: str, level: str, topic: str) -> Dict[str, Any]:
    max_tokens = int(os.getenv("HF_PASSAGE_MAX_TOKENS", PASSAGE_TOKENS_BY_LEVEL.get(level, 3600)))
    last_error: Optional[Exception] = None
    for attempt in range(1, 5):
        nonce = f"{int(time.time())}-{random.randint(100000, 999999)}"
        user_prompt = PASSAGE_GENERATION_PROMPT.format(
            level=level,
            topic=topic,
            length_guide=PASSAGE_LENGTH_GUIDE.get(level, PASSAGE_LENGTH_GUIDE["2"]),
            min_words=TARGET_WORDS_BY_LEVEL.get(level, 150),
            generation_id=nonce,
            attempt=attempt,
        )
        try:
            print(f"Live GenAI passage call | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens,
            )
            data = _extract_json(response.choices[0].message.content)
            return _validate_passage(data, level, topic)
        except Exception as exc:
            last_error = exc
            print(f"Passage generation attempt {attempt} failed: {type(exc).__name__}: {exc}")
    raise GenerationFailure(f"Live passage generation failed after 4 attempts: {type(last_error).__name__}: {last_error}")


def _generate_questions(client: InferenceClient, model: str, passage_data: Dict[str, Any], level: str, topic: str) -> List[Question]:
    max_tokens = int(os.getenv("HF_QUESTION_MAX_TOKENS", QUESTION_TOKENS_BY_LEVEL.get(level, 2800)))
    last_error: Optional[Exception] = None
    for attempt in range(1, 5):
        user_prompt = QUESTION_GENERATION_PROMPT.format(
            level=level,
            topic=topic,
            title=passage_data["passage_title"],
            passage_ru=passage_data["passage_ru"],
            attempt=attempt,
        )
        try:
            print(f"Live GenAI question call | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens,
            )
            data = _extract_json(response.choices[0].message.content)
            return _validate_questions(data)
        except Exception as exc:
            last_error = exc
            print(f"Question generation attempt {attempt} failed: {type(exc).__name__}: {exc}")
    raise GenerationFailure(f"Live question generation failed after 4 attempts: {type(last_error).__name__}: {last_error}")


def generate_reading_block(level: str, topic: str) -> TestBlock:
    """Generate one reading block using live GenAI only.

    There is intentionally no fallback template path. If GenAI fails, the caller should
    show the error and let the user retry/change model/token/provider.
    """
    token = os.getenv("HF_TOKEN")
    if not token:
        raise GenerationFailure("HF_TOKEN is missing. Add it as a Hugging Face Space secret. This app does not use fallback questions.")

    model = os.getenv("HF_TEXT_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    client = _make_client(token)
    passage_data = _generate_passage(client, model, level, topic)
    questions = _generate_questions(client, model, passage_data, level, topic)

    return TestBlock(
        skill="reading",
        ilr_level=level,
        topic=topic,
        passage_title=passage_data["passage_title"],
        passage_ru=passage_data["passage_ru"],
        questions=questions,
        generation_source="live",
        generation_error=passage_data.get("length_note", ""),
    )
