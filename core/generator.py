from __future__ import annotations

import json
import os
import random
import re
import time
import tempfile
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .prompts import (
    GENERATION_SYSTEM_PROMPT,
    ILR_STRUCTURE_RULES,
    PASSAGE_EXPANSION_PROMPT,
    PASSAGE_GENERATION_PROMPT,
    QUESTION_GENERATION_PROMPT,
    LISTENING_STRUCTURE_RULES,
    LISTENING_GENERATION_PROMPT,
    LISTENING_QUESTION_GENERATION_PROMPT,
)
from .schema import Question, TestBlock

load_dotenv()

# Output budgets. These are maximum output ceilings, not minimums. Minimum length is enforced by
# prompt + validation + expansion retry logic below.
PASSAGE_TOKENS_BY_LEVEL = {
    "0": 700,
    "0+": 900,
    "1": 1200,
    "1+": 1800,
    "2": 2600,
    "2+": 3600,
    "3": 5000,
}
QUESTION_TOKENS_BY_LEVEL = {
    "0": 1200,
    "0+": 1400,
    "1": 1600,
    "1+": 1800,
    "2": 2200,
    "2+": 2600,
    "3": 3000,
}

# Speed-first defaults for Hugging Face Spaces.
# No template fallback. No long retry loops.
# If the model produces a usable but short live passage, the app accepts it and moves on.
PASSAGE_MAX_ATTEMPTS = int(os.getenv("PASSAGE_MAX_ATTEMPTS", "1"))
QUESTION_MAX_ATTEMPTS = int(os.getenv("QUESTION_MAX_ATTEMPTS", "2"))
ENABLE_PASSAGE_EXPANSION = os.getenv("ENABLE_PASSAGE_EXPANSION", "false").strip().lower() in {"1", "true", "yes", "on"}

# No template fallback. We do not reject live GenAI just because it is short.
# Length/paragraph targets are preferred targets; after retries, the app uses the best live GenAI output.
ABSOLUTE_MIN_WORDS_BY_LEVEL = {"0": 1, "0+": 1, "1": 1, "1+": 1, "2": 1, "2+": 1, "3": 1}

class GenerationFailure(RuntimeError):
    """Raised when live GenAI generation fails. There is intentionally no template fallback."""


def _rules(level: str) -> Dict[str, Any]:
    return ILR_STRUCTURE_RULES.get(level, ILR_STRUCTURE_RULES["2"])


def _paragraph_schema_items(paragraphs: int, label: str = "Russian paragraph") -> str:
    # JSON example lines used in prompts. Keeping this dynamic prevents the model
    # from copying a one-item array when multiple paragraphs are required.
    return ",\n    ".join(f'"{label} {i}"' for i in range(1, paragraphs + 1))


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from model output.

    Some hosted chat models return almost-valid JSON with raw newline/control
    characters inside string values, especially when generating Russian paragraphs.
    Python's default json.loads(strict=True) rejects those.  We first try normal
    JSON, then retry with strict=False, which allows those control characters
    inside strings while still requiring the object structure to be valid.
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return a complete JSON object.")

    payload = text[start : end + 1]
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        # Handles raw line breaks/tabs inside JSON string values.
        try:
            return json.JSONDecoder(strict=False).decode(payload)
        except json.JSONDecodeError as exc:
            preview = payload[:600].replace("\n", " ")
            raise ValueError(f"Could not parse model JSON: {exc}. Output preview: {preview}") from exc


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

    # Prefer passage_paragraphs because it avoids invalid JSON caused by raw newlines
    # inside a single passage_ru string. If an older model response returns passage_ru,
    # keep supporting it for compatibility.
    raw_paragraphs = data.get("passage_paragraphs")
    if isinstance(raw_paragraphs, list):
        paragraphs_list = [str(p).strip() for p in raw_paragraphs if str(p).strip()]
        passage_ru = "\n\n".join(paragraphs_list).strip()
        paragraphs = len(paragraphs_list)
    else:
        passage_ru = str(data.get("passage_ru", "")).strip()
        paragraphs = _paragraph_count(passage_ru)

    if not title:
        raise ValueError("Generated passage_title is empty.")
    if not passage_ru:
        raise ValueError("Generated passage content is empty.")
    if _has_bad_repetition(passage_ru):
        raise ValueError("Generated passage contains repeated consecutive sentences.")

    words = _word_count(passage_ru)
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
    common = dict(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.25,
        top_p=0.9,
    )

    # Ask providers that support OpenAI-style structured JSON mode to enforce a
    # JSON object. Some HF providers ignore this or raise TypeError, so we fall
    # back safely.
    try:
        return client.chat.completions.create(
            **common,
            response_format={"type": "json_object"},
        )
    except TypeError:
        try:
            return client.chat.completions.create(**common)
        except TypeError as first_error:
            try:
                legacy_client = InferenceClient(model=model, token=os.getenv("HF_TOKEN"))
                legacy_common = dict(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.25,
                    top_p=0.9,
                )
                try:
                    return legacy_client.chat.completions.create(
                        **legacy_common,
                        response_format={"type": "json_object"},
                    )
                except TypeError:
                    return legacy_client.chat.completions.create(**legacy_common)
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
        official_basis=r["official_basis"],
        text_requirements=r["text_requirements"],
        paragraph_items=_paragraph_schema_items(int(r["paragraphs"])),
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
        official_basis=r["official_basis"],
        text_requirements=r["text_requirements"],
        current_words=passage_data.get("word_count", 0),
        current_paragraphs=passage_data.get("paragraph_count", 0),
        title=passage_data["passage_title"].replace('"', "'"),
        passage_ru=passage_data["passage_ru"],
        paragraph_items=_paragraph_schema_items(int(r["paragraphs"]), "Expanded Russian paragraph"),
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

    for attempt in range(1, max(1, PASSAGE_MAX_ATTEMPTS) + 1):
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

            # Speed-first behavior: a valid live GenAI passage is usable even if it is short.
            # This avoids slow generation loops on Hugging Face Spaces.
            if ok or not ENABLE_PASSAGE_EXPANSION:
                return passage

            # Optional expansion. Disabled by default because it adds another model call and slows the app.
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
            return expanded

        except Exception as exc:
            last_error = exc
            print(f"Passage generation attempt {attempt} failed: {type(exc).__name__}: {exc}")

    if best is not None:
        return best
    raise GenerationFailure(f"Live passage generation failed after {max(1, PASSAGE_MAX_ATTEMPTS)} attempt(s): {type(last_error).__name__}: {last_error}")


def _generate_questions(client: InferenceClient, model: str, passage_data: Dict[str, Any], level: str, topic: str) -> List[Question]:
    max_tokens = int(os.getenv("HF_QUESTION_MAX_TOKENS", QUESTION_TOKENS_BY_LEVEL.get(level, 3200)))
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, QUESTION_MAX_ATTEMPTS) + 1):
        user_prompt = QUESTION_GENERATION_PROMPT.format(
            level=level,
            topic=topic,
            title=passage_data["passage_title"],
            passage_ru=passage_data["passage_ru"],
            attempt=attempt,
            official_basis=_rules(level)["official_basis"],
            question_profile=_rules(level)["question_profile"],
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
    raise GenerationFailure(f"Live question generation failed after {max(1, QUESTION_MAX_ATTEMPTS)} attempt(s): {type(last_error).__name__}: {last_error}")



def _listening_rules(level: str) -> Dict[str, Any]:
    return LISTENING_STRUCTURE_RULES.get(level, LISTENING_STRUCTURE_RULES["2"])


def _segment_schema_items(segments: int) -> str:
    return ",\n    ".join(f'"Russian spoken segment {i}"' for i in range(1, segments + 1))


def _listening_prompt(level: str, topic: str, attempt: int) -> str:
    r = _listening_rules(level)
    nonce = f"{int(time.time())}-{random.randint(100000, 999999)}"
    return LISTENING_GENERATION_PROMPT.format(
        level=level,
        topic=topic,
        generation_id=nonce,
        attempt=attempt,
        min_words=r["min_words"],
        max_words=r["max_words"],
        segments=r["segments"],
        style=r["style"],
        delivery=r["delivery"],
        official_basis=r["official_basis"],
        text_requirements=r["text_requirements"],
        segment_items=_segment_schema_items(int(r["segments"])),
    )


def _validate_listening_script(data: Dict[str, Any], level: str, topic: str) -> Dict[str, Any]:
    title = str(data.get("passage_title", "")).strip()
    raw_segments = data.get("script_segments")
    if isinstance(raw_segments, list):
        segments_list = [str(seg).strip() for seg in raw_segments if str(seg).strip()]
        passage_ru = "\n\n".join(segments_list).strip()
        segment_count = len(segments_list)
    else:
        passage_ru = str(data.get("passage_ru", data.get("script_ru", ""))).strip()
        segment_count = _paragraph_count(passage_ru)

    if not title:
        raise ValueError("Generated listening title is empty.")
    if not passage_ru:
        raise ValueError("Generated listening script is empty.")
    if _has_bad_repetition(passage_ru):
        raise ValueError("Generated listening script contains repeated consecutive sentences.")

    words = _word_count(passage_ru)
    r = _listening_rules(level)
    min_words = int(r["min_words"])
    required_segments = int(r["segments"])
    if words < 1:
        raise ValueError("Generated listening script is empty or unusable.")

    if words < min_words or segment_count < required_segments:
        note = (
            f"Live GenAI listening script accepted, but it is below the preferred ILR {level} structure "
            f"({words}/{min_words} words, {segment_count}/{required_segments} spoken segments)."
        )
    else:
        note = f"Live GenAI listening script meets ILR {level} structure target ({words} words, {segment_count} spoken segments)."

    return {
        "skill": "listening",
        "ilr_level": str(data.get("ilr_level", level)).strip() or level,
        "topic": str(data.get("topic", topic)).strip() or topic,
        "passage_title": title,
        "passage_ru": passage_ru,
        "length_note": note,
        "word_count": words,
        "segment_count": segment_count,
    }


def _generate_listening_script(client: InferenceClient, model: str, level: str, topic: str) -> Dict[str, Any]:
    max_tokens = int(os.getenv("HF_LISTENING_MAX_TOKENS", PASSAGE_TOKENS_BY_LEVEL.get(level, 2600)))
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, PASSAGE_MAX_ATTEMPTS) + 1):
        try:
            print(f"Live GenAI listening script call | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": _listening_prompt(level, topic, attempt)},
                ],
                max_tokens,
            )
            data = _extract_json(response.choices[0].message.content)
            script = _validate_listening_script(data, level, topic)
            r = _listening_rules(level)
            print(f"Listening script attempt {attempt} quality: word count {script['word_count']}/{r['min_words']}; segments {script['segment_count']}/{r['segments']}")
            return script
        except Exception as exc:
            last_error = exc
            print(f"Listening script generation attempt {attempt} failed: {type(exc).__name__}: {exc}")
    raise GenerationFailure(f"Live listening script generation failed after {max(1, PASSAGE_MAX_ATTEMPTS)} attempt(s): {type(last_error).__name__}: {last_error}")


def _generate_listening_questions(client: InferenceClient, model: str, passage_data: Dict[str, Any], level: str, topic: str) -> List[Question]:
    max_tokens = int(os.getenv("HF_LISTENING_QUESTION_MAX_TOKENS", QUESTION_TOKENS_BY_LEVEL.get(level, 2200)))
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, QUESTION_MAX_ATTEMPTS) + 1):
        r = _listening_rules(level)
        user_prompt = LISTENING_QUESTION_GENERATION_PROMPT.format(
            level=level,
            topic=topic,
            title=passage_data["passage_title"],
            passage_ru=passage_data["passage_ru"],
            attempt=attempt,
            official_basis=r["official_basis"],
            question_profile=r["question_profile"],
        )
        try:
            print(f"Live GenAI listening question call | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt}")
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
            print(f"Listening question generation attempt {attempt} failed: {type(exc).__name__}: {exc}")
    raise GenerationFailure(f"Live listening question generation failed after {max(1, QUESTION_MAX_ATTEMPTS)} attempt(s): {type(last_error).__name__}: {last_error}")


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _make_tts_audio(text: str, level: str) -> str:
    """Create Russian MP3 audio for listening practice using edge-tts."""
    try:
        import edge_tts
    except Exception as exc:
        raise GenerationFailure("edge-tts is not installed. Add edge-tts to requirements.txt and restart the Space.") from exc

    voice = os.getenv("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural")
    # Slightly slower for low levels; normal for 2+ and 3.
    rate_by_level = {
        "0": "-25%",
        "0+": "-20%",
        "1": "-15%",
        "1+": "-10%",
        "2": "-5%",
        "2+": "+0%",
        "3": "+0%",
    }
    rate = os.getenv("EDGE_TTS_RATE", rate_by_level.get(level, "-5%"))
    out_path = os.path.join(tempfile.gettempdir(), f"ilr_listening_{int(time.time())}_{random.randint(100000,999999)}.mp3")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    _run_async(communicate.save(out_path))
    return out_path


def generate_listening_block(level: str, topic: str) -> TestBlock:
    """Generate one listening block using live GenAI + generated Russian TTS audio. No template fallback."""
    token = os.getenv("HF_TOKEN")
    if not token:
        raise GenerationFailure("HF_TOKEN is missing. Add it as a Hugging Face Space secret. This app does not use fallback questions.")

    model = os.getenv("HF_TEXT_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    client = _make_client(token)
    script_data = _generate_listening_script(client, model, level, topic)
    questions = _generate_listening_questions(client, model, script_data, level, topic)
    audio_path = _make_tts_audio(script_data["passage_ru"], level)

    return TestBlock(
        skill="listening",
        ilr_level=level,
        topic=topic,
        passage_title=script_data["passage_title"],
        passage_ru=script_data["passage_ru"],
        questions=questions,
        generation_source="live",
        generation_error=script_data.get("length_note", ""),
        audio_path=audio_path,
    )

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
