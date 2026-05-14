from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .prompts import (
    GENERATION_SYSTEM_PROMPT,
    ILR_STRUCTURE_RULES,
    PASSAGE_EXPANSION_PROMPT,
    PASSAGE_GENERATION_PROMPT,
    QUESTION_GENERATION_PROMPT,
)
from .schema import Question, TestBlock

load_dotenv()

# Output budgets. These are maximum output ceilings, not minimums. Minimum length is enforced by
# prompt + validation + expansion retry logic below.
PASSAGE_TOKENS_BY_LEVEL = {
    "0+": 1600,
    "1": 2200,
    "1+": 3200,
    "2": 4800,
    "2+": 6500,
    "3": 8500,
}
QUESTION_TOKENS_BY_LEVEL = {
    "0+": 1800,
    "1": 2200,
    "1+": 2600,
    "2": 3200,
    "2+": 3800,
    "3": 4400,
}

# No template fallback. We do not reject live GenAI just because it is short.
# Length/paragraph targets are preferred targets; after retries, the app uses the best live GenAI output.
ABSOLUTE_MIN_WORDS_BY_LEVEL = {"0+": 1, "1": 1, "1+": 1, "2": 1, "2+": 1, "3": 1}

class GenerationFailure(RuntimeError):
    """Raised when live GenAI generation fails. There is intentionally no template fallback."""


def _rules(level: str) -> Dict[str, Any]:
    return ILR_STRUCTURE_RULES.get(level, ILR_STRUCTURE_RULES["2"])


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
    # Counts whitespace-separated Russian/English word-like units. This is not a token count.
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _paragraph_count(text: str) -> int:
    # Prefer actual blank-line paragraphing. If the model returns single newlines, count those too.
    raw = text.strip()
    if not raw:
        return 0
    blank_split = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
    if len(blank_split) > 1:
        return len(blank_split)
    line_split = [p.strip() for p in raw.splitlines() if p.strip()]
    return max(1, len(line_split))


def _has_bad_repetition(text: str) -> bool:
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if p.strip()]
    if len(parts) < 2:
        return False
    return any(parts[i] == parts[i - 1] for i in range(1, len(parts)))


def _quality_status(passage: Dict[str, Any], level: str) -> Tuple[bool, str]:
    rules = _rules(level)
    min_words = int(rules["min_words"])
    required_paragraphs = int(rules["paragraphs"])
    words = int(passage.get("word_count", 0))
    paragraphs = int(passage.get("paragraph_count", 0))

    missing = []
    if words < min_words:
        missing.append(f"word count {words}/{min_words}")
    if paragraphs < required_paragraphs:
        missing.append(f"paragraph count {paragraphs}/{required_paragraphs}")
    if missing:
        return False, "; ".join(missing)
    return True, f"meets target length ({words} words, {paragraphs} paragraphs)"


def _validate_passage(data: Dict[str, Any], level: str, topic: str) -> Dict[str, Any]:
    title = str(data.get("passage_title", "")).strip()
    passage_ru = str(data.get("passage_ru", "")).strip()
    if not title:
        raise ValueError("Generated passage_title is empty.")
    if not passage_ru:
        raise ValueError("Generated passage_ru is empty.")
    if _has_bad_repetition(passage_ru):
        raise ValueError("Generated passage contains repeated consecutive sentences.")

    words = _word_count(passage_ru)
    paragraphs = _paragraph_count(passage_ru)
    absolute_min = ABSOLUTE_MIN_WORDS_BY_LEVEL.get(level, 1)
    if words < absolute_min:
        raise ValueError("Generated passage is empty or unusable.")

    rules = _rules(level)
    min_words = int(rules["min_words"])
    required_paragraphs = int(rules["paragraphs"])
    note = ""
    if words < min_words or paragraphs < required_paragraphs:
        note = (
            f"Live GenAI passage accepted after retries, but it is below the preferred ILR {level} structure "
            f"({words}/{min_words} words, {paragraphs}/{required_paragraphs} paragraphs)."
        )
    else:
        note = f"Live GenAI passage meets ILR {level} structure target ({words} words, {paragraphs} paragraphs)."

    return {
        "skill": "reading",
        "ilr_level": str(data.get("ilr_level", level)).strip() or level,
        "topic": str(data.get("topic", topic)).strip() or topic,
        "passage_title": title,
        "passage_ru": passage_ru,
        "length_note": note,
        "word_count": words,
        "paragraph_count": paragraphs,
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
            temperature=0.45,
            top_p=0.9,
        )
    except TypeError as first_error:
        try:
            legacy_client = InferenceClient(model=model, token=os.getenv("HF_TOKEN"))
            return legacy_client.chat.completions.create(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.45,
                top_p=0.9,
            )
        except Exception:
            raise first_error


def _passage_prompt(level: str, topic: str, attempt: int) -> str:
    r = _rules(level)
    nonce = f"{int(time.time())}-{random.randint(100000, 999999)}"
    return PASSAGE_GENERATION_PROMPT.format(
        level=level,
        topic=topic,
        generation_id=nonce,
        attempt=attempt,
        min_words=r["min_words"],
        max_words=r["max_words"],
        paragraphs=r["paragraphs"],
        sentences_per_paragraph=r["sentences_per_paragraph"],
        description=r["description"],
    )


def _expand_prompt(level: str, topic: str, passage_data: Dict[str, Any]) -> str:
    r = _rules(level)
    return PASSAGE_EXPANSION_PROMPT.format(
        level=level,
        topic=topic,
        min_words=r["min_words"],
        max_words=r["max_words"],
        paragraphs=r["paragraphs"],
        sentences_per_paragraph=r["sentences_per_paragraph"],
        current_words=passage_data.get("word_count", 0),
        current_paragraphs=passage_data.get("paragraph_count", 0),
        title=passage_data["passage_title"].replace('"', "'"),
        passage_ru=passage_data["passage_ru"],
    )


def _generate_passage(client: InferenceClient, model: str, level: str, topic: str) -> Dict[str, Any]:
    max_tokens = int(os.getenv("HF_PASSAGE_MAX_TOKENS", PASSAGE_TOKENS_BY_LEVEL.get(level, 4800)))
    last_error: Optional[Exception] = None
    best: Optional[Dict[str, Any]] = None

    def remember(candidate: Dict[str, Any]):
        nonlocal best
        if best is None:
            best = candidate
            return
        # Prefer full target; otherwise prefer more words and then more paragraphs.
        candidate_ok, _ = _quality_status(candidate, level)
        best_ok, _ = _quality_status(best, level)
        if candidate_ok and not best_ok:
            best = candidate
        elif candidate_ok == best_ok:
            if (candidate.get("word_count", 0), candidate.get("paragraph_count", 0)) > (best.get("word_count", 0), best.get("paragraph_count", 0)):
                best = candidate

    for attempt in range(1, 5):
        try:
            print(f"Live GenAI passage call | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": _passage_prompt(level, topic, attempt)},
                ],
                max_tokens,
            )
            data = _extract_json(response.choices[0].message.content)
            passage = _validate_passage(data, level, topic)
            remember(passage)
            ok, reason = _quality_status(passage, level)
            print(f"Passage attempt {attempt} quality: {reason}")
            if ok:
                return passage

            # Expansion call: this is the key fix. Do not immediately accept short GenAI.
            print(f"Expanding passage attempt {attempt} because: {reason}")
            expand_response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": _expand_prompt(level, topic, passage)},
                ],
                max_tokens,
            )
            expanded_data = _extract_json(expand_response.choices[0].message.content)
            expanded = _validate_passage(expanded_data, level, topic)
            remember(expanded)
            ok, reason = _quality_status(expanded, level)
            print(f"Expanded passage attempt {attempt} quality: {reason}")
            if ok:
                return expanded

        except Exception as exc:
            last_error = exc
            print(f"Passage generation attempt {attempt} failed: {type(exc).__name__}: {exc}")

    if best is not None:
        # Still live GenAI, never a template. This prevents total failure while making status honest.
        return best
    raise GenerationFailure(f"Live passage generation failed after 4 attempts: {type(last_error).__name__}: {last_error}")


def _generate_questions(client: InferenceClient, model: str, passage_data: Dict[str, Any], level: str, topic: str) -> List[Question]:
    max_tokens = int(os.getenv("HF_QUESTION_MAX_TOKENS", QUESTION_TOKENS_BY_LEVEL.get(level, 3200)))
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
    """Generate one reading block using live GenAI only. No template fallback."""
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
