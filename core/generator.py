from __future__ import annotations

import json
import os
import random
import re
import time
import tempfile
import asyncio
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

try:
    from groq import Groq
except Exception:  # Groq is optional; app can still run with Hugging Face only.
    Groq = None

from .prompts import (
    GENERATION_SYSTEM_PROMPT,
    ILR_STRUCTURE_RULES,
    PASSAGE_EXPANSION_PROMPT,
    PASSAGE_GENERATION_PROMPT,
    QUESTION_GENERATION_PROMPT,
    LISTENING_STRUCTURE_RULES,
    LISTENING_GENERATION_PROMPT,
    LISTENING_EXPANSION_PROMPT,
    LISTENING_QUESTION_GENERATION_PROMPT,
    LISTENING_SCRIPT_REPAIR_PROMPT,
    LISTENING_QUESTION_REPAIR_PROMPT,
    LISTENING_QUESTION_AUDIT_PROMPT,
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
    "2": 3800,
    "2+": 5200,
    "3": 7600,
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
# No template fallback. For ILR 2 and above, the app does one short-output expansion pass by default.
PASSAGE_MAX_ATTEMPTS = int(os.getenv("PASSAGE_MAX_ATTEMPTS", "1"))
QUESTION_MAX_ATTEMPTS = int(os.getenv("QUESTION_MAX_ATTEMPTS", "2"))
ENABLE_PASSAGE_EXPANSION = os.getenv("ENABLE_PASSAGE_EXPANSION", "false").strip().lower() in {"1", "true", "yes", "on"}
# Enforce/expand longer upper-level blocks by default. This keeps low levels fast while preventing ILR 2+ from staying in the 100-word range.
ENFORCE_LENGTH_LEVELS = {x.strip() for x in os.getenv("ENFORCE_LENGTH_LEVELS", "2,2+,3").split(",") if x.strip()}
ENABLE_LISTENING_EXPANSION = os.getenv("ENABLE_LISTENING_EXPANSION", "true").strip().lower() in {"1", "true", "yes", "on"}

# Listening quality/speed controls.
# smart = audit only when the generated questions look risky (time math, vague importance, etc.).
# always = audit every listening block. off = skip audit entirely.
LISTENING_AUDIT_MODE = os.getenv("LISTENING_AUDIT_MODE", "smart").strip().lower()
LISTENING_PARALLEL_TTS = os.getenv("LISTENING_PARALLEL_TTS", "true").strip().lower() in {"1", "true", "yes", "on"}
AUDIT_TOKENS_BY_LEVEL = {
    "0": 900,
    "0+": 1000,
    "1": 1200,
    "1+": 1400,
    "2": 1600,
    "2+": 1800,
    "3": 2200,
}
ENABLE_LISTENING_QUESTION_AUDIT = os.getenv("ENABLE_LISTENING_QUESTION_AUDIT", "true").strip().lower() in {"1", "true", "yes", "on"}

# Deterministic listening quality gate. This catches the exact failure mode you saw:
# repeated listening-script status lines, weak ILR-3 detail-only questions, and ambiguous cause questions.
ENABLE_LISTENING_QUALITY_GATE = os.getenv("ENABLE_LISTENING_QUALITY_GATE", "true").strip().lower() in {"1", "true", "yes", "on"}
LISTENING_SCRIPT_REPAIR_MAX_ATTEMPTS = int(os.getenv("LISTENING_SCRIPT_REPAIR_MAX_ATTEMPTS", "1"))
LISTENING_QUESTION_REPAIR_MAX_ATTEMPTS = int(os.getenv("LISTENING_QUESTION_REPAIR_MAX_ATTEMPTS", "1"))
LISTENING_STRICT_SCRIPT_GATE = os.getenv("LISTENING_STRICT_SCRIPT_GATE", "false").strip().lower() in {"1", "true", "yes", "on"}

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


def _split_sentences(text: str) -> List[str]:
    """Lightweight sentence splitter for generated Russian/English text."""
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if s.strip()]


def _normalize_for_quality(text: str) -> str:
    """Normalize text for cheap repetition/quality checks without changing output."""
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[\u0301\u0300]", "", text)
    text = re.sub(r"[^0-9a-zа-яё\s]+", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _ngrams(words: List[str], n: int) -> List[str]:
    if len(words) < n:
        return []
    return [" ".join(words[i : i + n]) for i in range(0, len(words) - n + 1)]


def _jaccard(a: str, b: str) -> float:
    aw = set(_normalize_for_quality(a).split())
    bw = set(_normalize_for_quality(b).split())
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / max(1, len(aw | bw))


def _extract_cause_markers(text: str) -> List[str]:
    """Find simple Russian cause/explanation markers that can create ambiguous question keys."""
    norm = _normalize_for_quality(text)
    patterns = [
        r"причин[аоы]?\s+стало\s+[^.?!]{8,90}",
        r"причиной\s+стал[ао]?\s+[^.?!]{8,90}",
        r"произошл[ао]?\s+из\s+за\s+[^.?!]{8,90}",
        r"из\s+за\s+[^.?!]{8,90}",
        r"связано\s+с\s+[^.?!]{8,90}",
    ]
    markers: List[str] = []
    for pattern in patterns:
        markers.extend(re.findall(pattern, norm))
    # Keep unique shortened markers.
    unique: List[str] = []
    for m in markers:
        m = m.strip()
        if m and m not in unique:
            unique.append(m)
    return unique


def _has_preliminary_update_markers(text: str) -> bool:
    norm = _normalize_for_quality(text)
    preliminary = any(x in norm for x in ["по предварительным данным", "предварительная версия", "сначала", "первоначально"])
    updated = any(x in norm for x in ["по последним данным", "позже", "затем", "уточнили", "обновленная версия", "следствие установило"])
    return preliminary and updated


def _listening_script_quality_issues(script_data: Dict[str, Any], level: str) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for generated listening scripts.

    This is intentionally cheap/deterministic. It does not replace the model; it
    catches obvious bad generations before we spend time creating audio and questions.
    """
    if not ENABLE_LISTENING_QUALITY_GATE:
        return [], []

    text = script_data.get("passage_ru", "") or ""
    errors: List[str] = []
    warnings: List[str] = []
    norm_text = _normalize_for_quality(text)
    sentences = _split_sentences(text)
    normalized_sentences = [_normalize_for_quality(s) for s in sentences]

    # Repeated complete sentences anywhere, not just consecutive.
    seen: Dict[str, int] = {}
    for s in normalized_sentences:
        if len(s.split()) < 7:
            continue
        seen[s] = seen.get(s, 0) + 1
    repeated_sentences = [s for s, count in seen.items() if count >= 2]
    if repeated_sentences:
        errors.append("script repeats one or more full sentences instead of adding new information")

    # Repeated medium-length chunks catch slightly edited copy/paste loops.
    words = norm_text.split()
    repeated_12grams = [g for g, count in {g: _ngrams(words, 12).count(g) for g in set(_ngrams(words, 12))}.items() if count >= 2]
    if repeated_12grams:
        errors.append("script repeats the same 12-word status/update phrase more than once")

    # Segment-level similarity: paragraphs should advance, not restate.
    segments = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(segments) >= 2:
        for i in range(1, len(segments)):
            if _jaccard(segments[i - 1], segments[i]) > 0.58:
                warnings.append(f"spoken segment {i + 1} is too similar to segment {i}")

    # Cause ambiguity: acceptable only if explicitly framed as preliminary vs updated.
    causes = _extract_cause_markers(text)
    if len(causes) >= 2 and not _has_preliminary_update_markers(text):
        errors.append("script gives multiple causes for the same event without explaining preliminary vs later findings")
    elif len(causes) >= 2:
        warnings.append("script contains preliminary and later cause findings; questions must ask about the evolution, not one vague main cause")

    if level == "3":
        if int(script_data.get("segment_count", 0)) < 4:
            errors.append("ILR 3 listening script must have exactly four developed spoken segments")
        if _word_count(text) < int(_listening_rules(level)["min_words"]):
            warnings.append("ILR 3 script is below the target word count")
        # ILR 3 should have discourse markers/relationships, not just repeated facts.
        discourse_markers = ["однако", "при этом", "в то же время", "поэтому", "следовательно", "между тем", "по словам", "эксперты", "власти", "аналитики", "если"]
        if sum(1 for marker in discourse_markers if marker in norm_text) < 3:
            warnings.append("ILR 3 script may be too list-like; add relationship markers, viewpoints, or implications")

    return errors, warnings


def _append_quality_note(script_data: Dict[str, Any], note: str) -> Dict[str, Any]:
    note = note.strip()
    if not note:
        return script_data
    existing = script_data.get("length_note", "")
    script_data["length_note"] = f"{existing} {note}".strip()
    return script_data


def _listening_question_quality_issues(passage_data: Dict[str, Any], level: str, questions: List[Question]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for generated listening question sets."""
    if not ENABLE_LISTENING_QUALITY_GATE:
        return [], []

    errors: List[str] = []
    warnings: List[str] = []
    bundle = _question_text_bundle(questions)
    cause_markers = _extract_cause_markers(passage_data.get("passage_ru", ""))
    ambiguous_cause = len(cause_markers) >= 2

    simple_stems = ("how many", "when", "where", "who", "what number", "what time")
    simple_count = 0
    detail_count = 0
    higher_order_types = {"main idea", "inference", "speaker/writer intent", "cause and effect", "tone or attitude", "meaning from context", "relationship of ideas", "comprehension"}

    for q in questions:
        qtext = q.question.strip().lower()
        qtype = q.question_type.strip().lower()
        if qtype == "detail" or qtext.startswith(simple_stems):
            simple_count += 1
        if qtype == "detail":
            detail_count += 1
        if "main cause" in qtext and ambiguous_cause:
            errors.append("question asks for one vague main cause even though the script has preliminary/later cause information")
        if re.search(r"\bhow long\b|\bduration\b|\bcalculate\b|\bsubtract\b|\badd\b", qtext):
            errors.append("question requires duration/math or invites calculation")
        if not q.evidence.strip():
            errors.append(f"{q.id} has no Russian evidence")
        if len(q.evidence.split()) > 28:
            warnings.append(f"{q.id} evidence is too long; use a short Russian phrase or clause")

    if level == "3":
        if detail_count > 1 or simple_count > 1:
            errors.append("ILR 3 listening question set uses too many simple detail/extraction questions")
        higher_count = sum(1 for q in questions if q.question_type.strip().lower() in higher_order_types and q.question_type.strip().lower() != "detail")
        if higher_count < 3:
            errors.append("ILR 3 listening question set needs at least three higher-order questions")
        if any("how many" in q.question.lower() for q in questions):
            warnings.append("ILR 3 set includes a how-many question; use only if you intentionally want one simple detail item")

    if "not directly stated" in bundle or "outside knowledge" in bundle:
        errors.append("question or answer explanation suggests unsupported inference")

    return errors, warnings



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



def _questions_to_json(questions: List[Question]) -> str:
    payload = {
        "questions": [
            {
                "id": q.id,
                "question": q.question,
                "choices": q.choices,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "evidence": q.evidence,
                "question_type": q.question_type,
            }
            for q in questions
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _question_text_bundle(questions: List[Question]) -> str:
    parts: List[str] = []
    for q in questions:
        parts.extend([q.question, q.explanation, q.evidence, q.question_type])
        parts.extend(q.choices.values())
    return "\n".join(parts).lower()


def _should_audit_listening_questions(level: str, questions: List[Question]) -> Tuple[bool, str]:
    """Decide whether to spend an extra model call on listening question repair.

    The first prompt already bans unsupported answers and math. This smart gate
    keeps the app fast by auditing only when the generated questions show risk
    markers that commonly caused bad items.
    """
    if not ENABLE_LISTENING_QUESTION_AUDIT or LISTENING_AUDIT_MODE in {"0", "false", "no", "off"}:
        return False, "audit disabled"
    if LISTENING_AUDIT_MODE in {"1", "true", "yes", "on", "always"}:
        return True, "audit mode is always"

    bundle = _question_text_bundle(questions)
    risky_patterns = [
        r"\bhow long\b",
        r"\bduration\b",
        r"\bhow many hours\b",
        r"\bfrom .* to\b",
        r"\bbetween .* and\b",
        r"\bbefore\b",
        r"\bafter\b",
        r"\bearlier\b",
        r"\blater\b",
        r"\bcalculate\b",
        r"\bimportant\b",
        r"\bimply\b",
        r"\binfer\b",
        r"\bnot directly stated\b",
    ]
    for pattern in risky_patterns:
        if re.search(pattern, bundle):
            return True, f"risk marker matched: {pattern}"

    # Higher-level listening allows implication/tone, but the answer key quality
    # matters more there. Audit only if the item types themselves are higher-risk.
    risky_types = {"inference", "tone or attitude", "speaker/writer intent", "meaning from context"}
    if level in {"2+", "3"} and any(q.question_type.lower() in risky_types for q in questions):
        return True, "higher-level risky question type"

    return False, "no risky question markers"


def _audit_listening_questions(client: InferenceClient, model: str, passage_data: Dict[str, Any], level: str, topic: str, questions: List[Question]) -> List[Question]:
    """Run an optional GenAI audit for listening items.

    This improves quality, but it costs an extra model call. The default smart
    mode only audits risky question sets so listening blocks load faster.
    """
    should_audit, audit_reason = _should_audit_listening_questions(level, questions)
    if not should_audit:
        print(f"Listening question audit skipped: {audit_reason}")
        return questions

    max_tokens = int(os.getenv("HF_LISTENING_AUDIT_MAX_TOKENS", AUDIT_TOKENS_BY_LEVEL.get(level, 1600)))
    user_prompt = LISTENING_QUESTION_AUDIT_PROMPT.format(
        level=level,
        topic=topic,
        title=passage_data["passage_title"],
        passage_ru=passage_data["passage_ru"],
        questions_json=_questions_to_json(questions),
    )
    print(f"Live GenAI listening audit call | model={model} | level={level} | max_tokens={max_tokens} | reason={audit_reason}")
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

def _make_client(token: str) -> Dict[str, Any]:
    """Create GenAI clients.

    Default behavior is HF first, then Groq as a failsafe. This keeps the
    existing Hugging Face code path while avoiding total failure when HF
    Inference Providers hit credits/rate limits.

    Environment variables:
      GENAI_PROVIDER=hf_then_groq | groq | huggingface | groq_then_hf
      HF_TOKEN=...
      GROQ_API_KEY=...
      HF_TEXT_MODEL=...
      GROQ_MODEL=...
    """
    hf_provider = os.getenv("HF_PROVIDER", "auto").strip() or "auto"
    mode = os.getenv("GENAI_PROVIDER", "hf_then_groq").strip().lower()

    hf_client = None
    if token:
        try:
            hf_client = InferenceClient(provider=hf_provider, token=token)
        except TypeError:
            hf_client = InferenceClient(token=token)

    groq_client = None
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key and Groq is not None:
        groq_client = Groq(api_key=groq_key)

    if mode in {"groq", "groq_only"}:
        order = ["groq"]
    elif mode in {"huggingface", "hf", "hf_only"}:
        order = ["hf"]
    elif mode in {"groq_then_hf", "groq_first"}:
        order = ["groq", "hf"]
    else:
        order = ["hf", "groq"]

    return {"hf": hf_client, "groq": groq_client, "order": order, "mode": mode}


def _is_hf_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "402" in text
        or "payment required" in text
        or "depleted" in text
        or "monthly included credits" in text
        or "rate limit" in text
        or "429" in text
    )


def _call_hf_chat(client: Dict[str, Any], model: str, messages: List[Dict[str, str]], max_tokens: int):
    """Call the configured GenAI provider.

    The function name is kept as _call_hf_chat so the rest of the code does not
    need major changes. It now supports HF -> Groq fallback. All returned
    objects are OpenAI-compatible enough for response.choices[0].message.content.
    """
    last_error: Optional[Exception] = None

    for provider in client.get("order", ["hf", "groq"]):
        if provider == "hf":
            hf_client = client.get("hf")
            if hf_client is None:
                last_error = GenerationFailure("HF_TOKEN is missing or Hugging Face client was not created.")
                continue
            common = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.25,
                top_p=0.9,
            )
            try:
                print(f"GenAI provider call: huggingface | model={model} | max_tokens={max_tokens}")
                try:
                    return hf_client.chat.completions.create(
                        **common,
                        response_format={"type": "json_object"},
                    )
                except TypeError:
                    return hf_client.chat.completions.create(**common)
            except TypeError as first_error:
                # Some older HF clients expect the model at construction time.
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
                    last_error = first_error
                    continue
            except Exception as exc:
                last_error = exc
                # On HF credits/rate-limit errors, immediately try Groq if available.
                if _is_hf_limit_error(exc):
                    print(f"Hugging Face limit/credit issue detected; trying Groq failsafe: {type(exc).__name__}: {exc}")
                    continue
                print(f"Hugging Face call failed; trying next provider if available: {type(exc).__name__}: {exc}")
                continue

        elif provider == "groq":
            groq_client = client.get("groq")
            if groq_client is None:
                last_error = GenerationFailure("GROQ_API_KEY is missing or groq package is not installed.")
                continue
            groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
            common = dict(
                model=groq_model,
                messages=messages,
                temperature=0.25,
                top_p=0.9,
            )
            try:
                print(f"GenAI provider call: groq | model={groq_model} | max_tokens={max_tokens}")
                # Groq generally supports max_completion_tokens; keep a max_tokens fallback.
                try:
                    return groq_client.chat.completions.create(
                        **common,
                        max_completion_tokens=max_tokens,
                        response_format={"type": "json_object"},
                    )
                except TypeError:
                    try:
                        return groq_client.chat.completions.create(
                            **common,
                            max_tokens=max_tokens,
                            response_format={"type": "json_object"},
                        )
                    except TypeError:
                        return groq_client.chat.completions.create(
                            **common,
                            max_tokens=max_tokens,
                        )
            except Exception as exc:
                last_error = exc
                print(f"Groq call failed; trying next provider if available: {type(exc).__name__}: {exc}")
                continue

    raise GenerationFailure(f"All GenAI providers failed. Last error: {type(last_error).__name__}: {last_error}")


def _repair_listening_script_if_needed(client: Dict[str, Any], model: str, script_data: Dict[str, Any], level: str, topic: str, max_tokens: int) -> Dict[str, Any]:
    """Run a repair pass when deterministic checks find a bad listening script."""
    errors, warnings = _listening_script_quality_issues(script_data, level)
    if not errors and not warnings:
        return script_data

    issue_text = "\n".join([f"ERROR: {x}" for x in errors] + [f"WARNING: {x}" for x in warnings])
    print(f"Listening script quality gate found issues | errors={len(errors)} | warnings={len(warnings)} | issues={issue_text}")

    # Warnings alone should not slow every block down. Errors trigger repair; strict mode repairs warnings too.
    if not errors and not LISTENING_STRICT_SCRIPT_GATE:
        return _append_quality_note(script_data, f"Quality warning: {'; '.join(warnings)}")

    r = _listening_rules(level)
    best = script_data
    best_error_count = len(errors)
    last_error: Optional[Exception] = None

    for repair_attempt in range(1, max(0, LISTENING_SCRIPT_REPAIR_MAX_ATTEMPTS) + 1):
        try:
            user_prompt = LISTENING_SCRIPT_REPAIR_PROMPT.format(
                level=level,
                topic=topic,
                title=script_data["passage_title"].replace('"', "'"),
                quality_issues=issue_text,
                script_ru=script_data["passage_ru"],
                min_words=r["min_words"],
                max_words=r["max_words"],
                segments=r["segments"],
                segment_items=_segment_schema_items(int(r["segments"]), "Repaired Russian spoken segment"),
            )
            print(f"Live GenAI listening script repair call | model={model} | level={level} | attempt={repair_attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens,
            )
            repaired_data = _extract_json(response.choices[0].message.content)
            candidate = _validate_listening_script(repaired_data, level, topic)
            candidate_errors, candidate_warnings = _listening_script_quality_issues(candidate, level)
            print(
                f"Repaired listening script quality | errors={len(candidate_errors)} | warnings={len(candidate_warnings)} | "
                f"words={candidate['word_count']} | segments={candidate['segment_count']}"
            )
            if len(candidate_errors) < best_error_count:
                best = candidate
                best_error_count = len(candidate_errors)
            if not candidate_errors:
                if candidate_warnings:
                    candidate = _append_quality_note(candidate, f"Quality warning after repair: {'; '.join(candidate_warnings)}")
                else:
                    candidate = _append_quality_note(candidate, "Listening script passed quality gate after repair.")
                return candidate
        except Exception as exc:
            last_error = exc
            print(f"Listening script repair attempt {repair_attempt} failed: {type(exc).__name__}: {exc}")

    # Prefer a better repaired candidate if available; otherwise either fail in strict mode or continue with a clear note.
    if best is not script_data and best_error_count < len(errors):
        return _append_quality_note(best, "Listening script improved by quality repair but still has warnings/errors.")
    if LISTENING_STRICT_SCRIPT_GATE and errors:
        raise GenerationFailure(f"Listening script failed quality gate and repair failed: {'; '.join(errors)}. Last repair error: {last_error}")
    return _append_quality_note(script_data, f"Quality warning: {'; '.join(errors + warnings)}")


def _repair_listening_questions_if_needed(client: Dict[str, Any], model: str, passage_data: Dict[str, Any], level: str, topic: str, questions: List[Question]) -> List[Question]:
    """Repair question sets that pass JSON validation but are weak or unfair."""
    errors, warnings = _listening_question_quality_issues(passage_data, level, questions)
    if not errors and not warnings:
        return questions

    issue_text = "\n".join([f"ERROR: {x}" for x in errors] + [f"WARNING: {x}" for x in warnings])
    print(f"Listening question quality gate found issues | errors={len(errors)} | warnings={len(warnings)} | issues={issue_text}")

    # Warnings alone do not require another model call unless audit mode is always.
    if not errors and LISTENING_AUDIT_MODE not in {"always", "1", "true", "yes", "on"}:
        return questions

    max_tokens = int(os.getenv("HF_LISTENING_AUDIT_MAX_TOKENS", AUDIT_TOKENS_BY_LEVEL.get(level, 1800)))
    best = questions
    best_error_count = len(errors)

    for repair_attempt in range(1, max(0, LISTENING_QUESTION_REPAIR_MAX_ATTEMPTS) + 1):
        try:
            user_prompt = LISTENING_QUESTION_REPAIR_PROMPT.format(
                level=level,
                topic=topic,
                title=passage_data["passage_title"],
                passage_ru=passage_data["passage_ru"],
                questions_json=_questions_to_json(questions),
                quality_issues=issue_text,
            )
            print(f"Live GenAI listening question repair call | model={model} | level={level} | attempt={repair_attempt}")
            response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens,
            )
            repaired_data = _extract_json(response.choices[0].message.content)
            candidate = _validate_questions(repaired_data)
            candidate_errors, candidate_warnings = _listening_question_quality_issues(passage_data, level, candidate)
            print(f"Repaired listening question quality | errors={len(candidate_errors)} | warnings={len(candidate_warnings)}")
            if len(candidate_errors) < best_error_count:
                best = candidate
                best_error_count = len(candidate_errors)
            if not candidate_errors:
                return candidate
        except Exception as exc:
            print(f"Listening question repair attempt {repair_attempt} failed: {type(exc).__name__}: {exc}")

    return best


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

            # Low levels can remain fast. ILR 2+ gets one expansion pass when too short.
            should_expand = (not ok) and (ENABLE_PASSAGE_EXPANSION or level in ENFORCE_LENGTH_LEVELS)
            if ok or not should_expand:
                return passage

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
            return expanded if ok else (best or expanded)

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


def _segment_schema_items(segments: int, label: str = "Russian spoken segment") -> str:
    return ",\n    ".join(f'"{label} {i}"' for i in range(1, segments + 1))


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


def _listening_expand_prompt(level: str, topic: str, script_data: Dict[str, Any]) -> str:
    r = _listening_rules(level)
    return LISTENING_EXPANSION_PROMPT.format(
        level=level,
        topic=topic,
        min_words=r["min_words"],
        max_words=r["max_words"],
        segments=r["segments"],
        style=r["style"],
        delivery=r["delivery"],
        official_basis=r["official_basis"],
        text_requirements=r["text_requirements"],
        current_words=script_data.get("word_count", 0),
        current_segments=script_data.get("segment_count", 0),
        title=script_data["passage_title"].replace('"', "'"),
        script_ru=script_data["passage_ru"],
        segment_items=_segment_schema_items(int(r["segments"]), "Expanded Russian spoken segment"),
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
            script = _repair_listening_script_if_needed(client, model, script, level, topic, max_tokens)
            r = _listening_rules(level)
            print(f"Listening script attempt {attempt} quality: word count {script['word_count']}/{r['min_words']}; segments {script['segment_count']}/{r['segments']}")

            too_short = script["word_count"] < int(r["min_words"]) or script["segment_count"] < int(r["segments"])
            should_expand = too_short and ENABLE_LISTENING_EXPANSION and level in ENFORCE_LENGTH_LEVELS
            if not should_expand:
                return script

            print(f"Expanding listening script attempt {attempt} because: word count {script['word_count']}/{r['min_words']}; segments {script['segment_count']}/{r['segments']}")
            expand_response = _call_hf_chat(
                client,
                model,
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": _listening_expand_prompt(level, topic, script)},
                ],
                max_tokens,
            )
            expanded_data = _extract_json(expand_response.choices[0].message.content)
            expanded = _validate_listening_script(expanded_data, level, topic)
            expanded = _repair_listening_script_if_needed(client, model, expanded, level, topic, max_tokens)
            print(f"Expanded listening script attempt {attempt} quality: word count {expanded['word_count']}/{r['min_words']}; segments {expanded['segment_count']}/{r['segments']}")
            return expanded if expanded["word_count"] >= int(r["min_words"]) else (expanded if expanded["word_count"] >= script["word_count"] else script)
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
            questions = _validate_questions(data)
            try:
                questions = _audit_listening_questions(client, model, passage_data, level, topic, questions)
            except Exception as audit_exc:
                # Do not crash the app if the optional GenAI audit fails.
                # A deterministic quality gate still runs below.
                print(f"Listening question audit failed; continuing to deterministic gate: {type(audit_exc).__name__}: {audit_exc}")
            return _repair_listening_questions_if_needed(client, model, passage_data, level, topic, questions)
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


def _normalize_tts_text(text: str) -> str:
    """Normalize generated Russian script before TTS.

    Edge TTS can occasionally cut or mishandle long multi-paragraph text when it is
    sent as one large request. Normalizing and chunking keeps the full listening
    script intact.
    """
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("—", " — ").replace("–", " — ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_tts_text(text: str, max_chars: int = 900) -> List[str]:
    """Split text into TTS-safe chunks without dropping any content."""
    text = _normalize_tts_text(text)
    if not text:
        return []

    # Prefer paragraph boundaries first.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks: List[str] = []

    def add_piece(piece: str):
        piece = piece.strip()
        if not piece:
            return
        if len(piece) <= max_chars:
            chunks.append(piece)
            return
        # Split oversized paragraph by sentence boundaries.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", piece) if s.strip()]
        buf = ""
        for sent in sentences:
            if not buf:
                buf = sent
            elif len(buf) + 1 + len(sent) <= max_chars:
                buf += " " + sent
            else:
                chunks.append(buf.strip())
                buf = sent
        if buf:
            chunks.append(buf.strip())

    for paragraph in paragraphs or [text]:
        add_piece(paragraph)

    # Last-resort hard split for any still oversized chunks.
    safe_chunks: List[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            safe_chunks.append(chunk)
        else:
            for i in range(0, len(chunk), max_chars):
                safe_chunks.append(chunk[i : i + max_chars].strip())
    return [c for c in safe_chunks if c]


def _concat_mp3_files(segment_paths: List[str], out_path: str) -> None:
    """Concatenate MP3 segments into one playable MP3.

    Prefer ffmpeg's concat demuxer when available. If ffmpeg is unavailable in the
    hosting image, fall back to byte concatenation, which most browsers can play
    for MP3 streams generated with the same codec/voice settings.
    """
    if not segment_paths:
        raise GenerationFailure("TTS produced no audio segments.")
    if len(segment_paths) == 1:
        shutil.copyfile(segment_paths[0], out_path)
        return

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        list_path = out_path + ".txt"
        with open(list_path, "w", encoding="utf-8") as f:
            for seg in segment_paths:
                # ffmpeg concat file format. Paths are temp-generated, but still escape quotes.
                f.write("file '" + seg.replace("'", "'\\''") + "'\n")
        try:
            subprocess.run(
                [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        finally:
            try:
                os.remove(list_path)
            except OSError:
                pass

    # Fallback: append MP3 byte streams. This is not as clean as ffmpeg, but it
    # avoids losing audio if ffmpeg is not installed.
    with open(out_path, "wb") as outfile:
        for seg in segment_paths:
            with open(seg, "rb") as infile:
                shutil.copyfileobj(infile, outfile)


def _make_tts_audio(text: str, level: str, voice_label: str | None = None, speech_rate_label: str | None = None) -> str:
    """Create Russian MP3 audio for listening practice using edge-tts.

    The old version sent the full generated script to Edge TTS in one request. For
    longer ILR 2+/3 scripts, that can result in incomplete audio on Spaces. This
    version chunks the script, generates each chunk, then concatenates the MP3s so
    the full transcript is represented in the final audio file.
    """
    try:
        import edge_tts
    except Exception as exc:
        raise GenerationFailure("edge-tts is not installed. Add edge-tts to requirements.txt and restart the Space.") from exc

    voice_map = {
        "Russian Female - Svetlana": "ru-RU-SvetlanaNeural",
        "Russian Male - Dmitry": "ru-RU-DmitryNeural",
    }
    selected_voice = voice_map.get(voice_label or "", None)
    voice = selected_voice or os.getenv("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural")

    # Slightly slower for low levels; normal for 2+ and 3.
    auto_rate_by_level = {
        "0": "-25%",
        "0+": "-20%",
        "1": "-15%",
        "1+": "-10%",
        "2": "-5%",
        "2+": "+0%",
        "3": "+0%",
    }
    rate_map = {
        "Auto by ILR level": auto_rate_by_level.get(level, "-5%"),
        "Very slow training": "-25%",
        "Slow training": "-15%",
        "Slightly slow": "-8%",
        "Normal": "+0%",
        "Fast": "+10%",
    }
    selected_rate = rate_map.get(speech_rate_label or "", None)
    rate = selected_rate or os.getenv("EDGE_TTS_RATE", auto_rate_by_level.get(level, "-5%"))

    max_chars = int(os.getenv("EDGE_TTS_MAX_CHARS", "900"))
    chunks = _split_tts_text(text, max_chars=max_chars)
    if not chunks:
        raise GenerationFailure("Cannot create listening audio because the generated script is empty.")

    base = f"ilr_listening_{int(time.time())}_{random.randint(100000,999999)}"
    tmp_dir = tempfile.gettempdir()
    out_path = os.path.join(tmp_dir, f"{base}.mp3")
    segment_paths: List[str] = []

    try:
        for idx, chunk in enumerate(chunks, start=1):
            seg_path = os.path.join(tmp_dir, f"{base}_part{idx:02d}.mp3")
            communicate = edge_tts.Communicate(text=chunk, voice=voice, rate=rate)
            _run_async(communicate.save(seg_path))
            if not os.path.exists(seg_path) or os.path.getsize(seg_path) < 1024:
                raise GenerationFailure(f"TTS segment {idx} was not created correctly.")
            segment_paths.append(seg_path)

        _concat_mp3_files(segment_paths, out_path)
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 1024:
            raise GenerationFailure("Final TTS audio file was not created correctly.")
        print(
            f"TTS audio created | chunks={len(chunks)} | chars={len(_normalize_tts_text(text))} | "
            f"bytes={os.path.getsize(out_path)} | path={out_path}"
        )
        return out_path
    finally:
        # Keep the final output but remove intermediate segment files.
        for seg in segment_paths:
            try:
                os.remove(seg)
            except OSError:
                pass


def generate_listening_block(level: str, topic: str, voice_label: str | None = None, speech_rate_label: str | None = None) -> TestBlock:
    """Generate one listening block using live GenAI + generated Russian TTS audio. No template fallback.

    Speed optimization: after the script is generated, question generation and
    MP3 voice creation run in parallel because both only depend on the script.
    """
    token = os.getenv("HF_TOKEN", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not token and not groq_key:
        raise GenerationFailure("No GenAI key found. Add HF_TOKEN and/or GROQ_API_KEY as Space secrets. This app does not use fallback questions.")

    model = os.getenv("HF_TEXT_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    client = _make_client(token)
    script_data = _generate_listening_script(client, model, level, topic)

    if LISTENING_PARALLEL_TTS:
        with ThreadPoolExecutor(max_workers=2) as executor:
            questions_future = executor.submit(_generate_listening_questions, client, model, script_data, level, topic)
            audio_future = executor.submit(_make_tts_audio, script_data["passage_ru"], level, voice_label, speech_rate_label)
            questions = questions_future.result()
            audio_path = audio_future.result()
    else:
        questions = _generate_listening_questions(client, model, script_data, level, topic)
        audio_path = _make_tts_audio(script_data["passage_ru"], level, voice_label, speech_rate_label)

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
    token = os.getenv("HF_TOKEN", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not token and not groq_key:
        raise GenerationFailure("No GenAI key found. Add HF_TOKEN and/or GROQ_API_KEY as Space secrets. This app does not use fallback questions.")

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
