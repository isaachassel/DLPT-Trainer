from __future__ import annotations

import hashlib
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Iterable

from .constants import LETTERS
from .models import PassageItem, QuestionItem, ValidationReport

ABSOLUTE_WORDS = {"always", "never", "only", "completely", "entirely", "must", "all", "none"}
OUTSIDE_KNOWLEDGE_MARKERS = {
    "outside knowledge",
    "general knowledge",
    "not stated in the passage",
    "based on what is commonly known",
}


def normalize_text(text: str) -> str:
    text = text.casefold().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def near_duplicate(a: str, b: str, threshold: float = 0.90) -> bool:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio() >= threshold


def _words(text: str) -> list[str]:
    return normalize_text(text).split()


def _cyrillic_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        return 0.0
    return sum(bool(re.fullmatch(r"[А-Яа-яЁё]", char)) for char in letters) / len(letters)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text.strip()) if part.strip()]


def _has_repeated_ngram(text: str, n: int = 9) -> bool:
    words = _words(text)
    if len(words) < n * 2:
        return False
    grams = [tuple(words[index:index + n]) for index in range(len(words) - n + 1)]
    return len(grams) != len(set(grams))


def _orientation_reveals_choice(question: QuestionItem, passage: PassageItem) -> bool:
    orientation = normalize_text(passage.orientation_en)
    correct = normalize_text(question.choices.get(question.correct_key, ""))
    if len(correct.split()) < 4:
        return False
    return correct in orientation or near_duplicate(correct, orientation, 0.92)


def validate_question(question: QuestionItem, passage: PassageItem) -> ValidationReport:
    checks: dict[str, bool] = {}
    failures: list[str] = []
    flags: list[str] = list(question.ambiguity_flags)
    choices = [question.choices.get(letter, "") for letter in LETTERS]
    normalized_choices = [normalize_text(choice) for choice in choices]

    checks["four_unique_choices"] = set(question.choices) == set(LETTERS) and len(set(normalized_choices)) == 4 and all(normalized_choices)
    checks["supported_key"] = question.correct_key in LETTERS and question.correct_key in question.choices
    checks["question_links_to_passage"] = question.passage_id == passage.id
    checks["question_operational_status"] = question.status == "active" and question.validation_status == "accepted"
    checks["stem_present"] = len(question.stem_en.strip()) >= 8
    checks["stem_is_primarily_english"] = _cyrillic_ratio(question.stem_en) < 0.75
    checks["choices_are_primarily_english"] = all(_cyrillic_ratio(choice) < 0.55 for choice in choices)
    checks["evidence_present"] = bool(question.evidence_ru.strip())
    evidence_words = len(_words(question.evidence_ru))
    checks["evidence_not_entire_passage"] = evidence_words <= max(24, int(passage.word_count * 0.35))
    checks["evidence_in_passage"] = bool(normalize_text(question.evidence_ru)) and normalize_text(question.evidence_ru) in normalize_text(passage.passage_ru)
    checks["rationale_present"] = len(question.rationale_en.strip()) >= 12
    checks["no_near_duplicate_choices"] = not any(
        near_duplicate(choices[i], choices[j], 0.84)
        for i in range(4) for j in range(i + 1, 4)
    )

    lengths = [max(1, len(choice.split())) for choice in choices]
    checks["no_extreme_length_leak"] = max(lengths) <= max(6, min(lengths) * 3 + 3)
    correct_words = set(_words(question.choices.get(question.correct_key, "")))
    distractor_absolute_counts = [len(set(_words(question.choices[letter])) & ABSOLUTE_WORDS) for letter in LETTERS if letter != question.correct_key]
    checks["no_absolute_word_leak"] = len(correct_words & ABSOLUTE_WORDS) <= max([1, *distractor_absolute_counts])
    checks["orientation_does_not_reveal_answer"] = not _orientation_reveals_choice(question, passage)
    checks["supported_question_type"] = bool(question.question_type.strip())
    checks["difficulty_is_finite"] = -4.0 <= float(question.provisional_difficulty) <= 4.0

    rationale_norm = normalize_text(question.rationale_en)
    if any(marker in rationale_norm for marker in OUTSIDE_KNOWLEDGE_MARKERS):
        flags.append("possible_outside_knowledge")
    if question.correct_key not in question.choices:
        flags.append("missing_correct_choice")

    for name, passed in checks.items():
        if not passed:
            failures.append(name)
    status = "accepted" if not failures and not flags else "rejected"
    return ValidationReport(
        status=status,
        deterministic_checks=checks,
        ambiguity_flags=sorted(set(flags)),
        failure_reasons=failures,
        proposed_answer=question.correct_key,
    )


def validate_passage(passage: PassageItem, questions: list[QuestionItem]) -> ValidationReport:
    sentence_norms = [normalize_text(sentence) for sentence in _sentences(passage.passage_ru) if len(_words(sentence)) >= 5]
    question_stems = [normalize_text(question.stem_en) for question in questions]
    exact_word_count = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)?", passage.passage_ru))
    reading_limit_ok = passage.skill != "reading" or exact_word_count <= 500
    listening_limit_ok = passage.skill != "listening" or exact_word_count <= 390

    checks = {
        "passage_present": bool(passage.passage_ru.strip()),
        "passage_is_predominantly_russian": _cyrillic_ratio(passage.passage_ru) >= 0.65,
        "orientation_present": len(passage.orientation_en.strip()) >= 10,
        "orientation_is_primarily_english": _cyrillic_ratio(passage.orientation_en) < 0.25,
        "word_count_matches": abs(passage.word_count - exact_word_count) <= 3,
        "reading_word_limit": reading_limit_ok,
        "listening_duration_proxy_limit": listening_limit_ok,
        "question_ids_match": set(passage.question_ids) == {question.id for question in questions},
        "all_questions_link_to_passage": all(question.passage_id == passage.id for question in questions),
        "bundle_size_valid": (1 <= len(questions) <= 5) if passage.skill == "reading" else (1 <= len(questions) <= 3),
        "passage_operational_status": passage.status == "active" and passage.validation_status == "accepted",
        "not_padded_repetition": len(sentence_norms) < 2 or len(sentence_norms) == len(set(sentence_norms)),
        "no_repeated_long_ngram": not _has_repeated_ngram(passage.passage_ru),
        "no_markup_artifacts": re.search(r"[<>{}\[\]|]", passage.passage_ru) is None,
        "unique_question_stems": len(question_stems) == len(set(question_stems)),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return ValidationReport(
        status="accepted" if not failures else "rejected",
        deterministic_checks=checks,
        failure_reasons=failures,
    )


def answer_position_balance(questions: Iterable[QuestionItem]) -> dict[str, int]:
    counts = Counter(question.correct_key for question in questions)
    return {letter: counts.get(letter, 0) for letter in LETTERS}


def bank_balance_passes(questions: Iterable[QuestionItem], tolerance: int = 4) -> bool:
    counts = answer_position_balance(questions)
    return max(counts.values(), default=0) - min(counts.values(), default=0) <= tolerance
