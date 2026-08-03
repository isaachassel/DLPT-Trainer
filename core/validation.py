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
    # Tokenize Han characters individually so hashes, evidence matching, and
    # near-duplicate checks work for unsegmented Mandarin text as well as for
    # space-delimited Russian/English.
    tokens = re.findall(r"[a-zа-я0-9]+|[\u3400-\u9fff]", text)
    return " ".join(tokens)




def evidence_traceability_score(quote: str, passage: str, anchor: str = "") -> float:
    """Return a soft 0..1 traceability score for verifier-supplied evidence.

    The operational question evidence remains subject to the hard exact-substring
    check in :func:`validate_question`. A blind verifier's quote is advisory: some
    hosted models paraphrase, shorten, change ``ё``/``е``, or add omitted-word
    ellipses even when they select the supported answer. That behavior must not
    discard an otherwise validated item.
    """
    quote_norm = normalize_text(quote)
    passage_norm = normalize_text(passage)
    anchor_norm = normalize_text(anchor)
    if not quote_norm or not passage_norm:
        return 0.0
    if quote_norm in passage_norm:
        return 1.0

    quote_tokens = [token for token in quote_norm.split() if len(token) >= 3]
    passage_tokens = set(passage_norm.split())
    anchor_tokens = set(anchor_norm.split())
    if not quote_tokens:
        return 0.0

    token_precision = sum(token in passage_tokens for token in quote_tokens) / len(quote_tokens)
    anchor_overlap = (
        sum(token in anchor_tokens for token in quote_tokens) / len(quote_tokens)
        if anchor_tokens else 0.0
    )

    # Compare against similarly sized passage windows so short omissions and
    # minor inflection differences receive partial credit without becoming a
    # semantic acceptance gate.
    passage_list = passage_norm.split()
    width = max(1, len(quote_tokens))
    best_fuzzy = 0.0
    for window_width in range(max(1, width - 2), min(len(passage_list), width + 3) + 1):
        for start in range(0, max(1, len(passage_list) - window_width + 1)):
            window = " ".join(passage_list[start:start + window_width])
            best_fuzzy = max(best_fuzzy, SequenceMatcher(None, quote_norm, window).ratio())

    return max(0.0, min(1.0, max(token_precision, anchor_overlap, best_fuzzy)))

def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def near_duplicate(a: str, b: str, threshold: float = 0.90) -> bool:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio() >= threshold


def choice_near_duplicate(a: str, b: str) -> bool:
    """Detect answer choices that are effectively duplicates without punishing parallel grammar.

    Multiple-choice distractors should usually share a grammatical frame. A raw string-similarity
    threshold can therefore reject valid contrasts such as "the road will open" versus "the road
    will close." This check removes common leading/trailing scaffolding and requires the remaining
    distinguishing content to be substantially the same before rejecting the pair.
    """
    left = normalize_text(a)
    right = normalize_text(b)
    if not left or not right:
        return True
    if left == right:
        return True

    left_tokens = left.split()
    right_tokens = right.split()
    prefix = 0
    while prefix < min(len(left_tokens), len(right_tokens)) and left_tokens[prefix] == right_tokens[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(left_tokens) - prefix, len(right_tokens) - prefix)
        and left_tokens[-(suffix + 1)] == right_tokens[-(suffix + 1)]
    ):
        suffix += 1

    left_core = left_tokens[prefix:len(left_tokens) - suffix if suffix else None]
    right_core = right_tokens[prefix:len(right_tokens) - suffix if suffix else None]
    if not left_core or not right_core:
        # One option merely adds/removes a tiny qualifier from the other.
        return abs(len(left_tokens) - len(right_tokens)) <= 2

    left_set = set(left_core)
    right_set = set(right_core)
    core_jaccard = len(left_set & right_set) / max(1, len(left_set | right_set))
    core_ratio = SequenceMatcher(None, " ".join(left_core), " ".join(right_core)).ratio()
    full_ratio = SequenceMatcher(None, left, right).ratio()

    # Require both lexical overlap and sequence similarity. Shared sentence frames alone are not enough.
    return (full_ratio >= 0.96 and core_jaccard >= 0.80) or (core_ratio >= 0.92 and core_jaccard >= 0.75)


def canonicalize_evidence_quote(passage: str, evidence: str, max_words: int = 24) -> str:
    """Return an exact, short passage span when the model supplied a verbose/normalized quote.

    This is a formatting repair only. Semantic support is still checked independently by the blind
    verifier. If no sufficiently traceable exact span can be found, the original evidence is returned
    and normal validation will reject it.
    """
    raw = evidence.strip()
    if not raw:
        return raw
    passage_norm = normalize_text(passage)
    raw_norm = normalize_text(raw)
    if raw_norm and raw_norm in passage_norm and len(_words(raw)) <= max_words:
        # Preserve the provider quote when it is already a short normalized substring.
        for candidate in re.split(r"(?<=[.!?…])\s+|[;:]\s*", passage):
            candidate = candidate.strip()
            if raw_norm == normalize_text(candidate) or raw_norm in normalize_text(candidate):
                if len(_words(candidate)) <= max_words:
                    return candidate
        return raw

    candidates: list[str] = []
    for sentence in _sentences(passage):
        parts = [sentence, *re.split(r"[,;:]\s*", sentence)]
        for part in parts:
            part = part.strip(" \t\n—–-")
            words = _words(part)
            if 2 <= len(words) <= max_words and part not in candidates:
                candidates.append(part)

    evidence_tokens = set(_words(raw))
    best: tuple[float, str] | None = None
    for candidate in candidates:
        candidate_norm = normalize_text(candidate)
        candidate_tokens = set(_words(candidate))
        overlap = len(evidence_tokens & candidate_tokens) / max(1, len(candidate_tokens))
        fuzzy = SequenceMatcher(None, raw_norm, candidate_norm).ratio()
        score = max(overlap, fuzzy)
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1] if best and best[0] >= 0.68 else raw


def _words(text: str) -> list[str]:
    return normalize_text(text).split()


def choice_length_leakage_flags(question: QuestionItem) -> list[str]:
    """Return material answer-length cues without invalidating legacy banks.

    Starter content predates this diagnostic, so the operational validator keeps
    its broad hard limit for backward compatibility. Freshly generated items use
    these stricter flags as repair instructions before they can be stored.
    """

    lengths = {letter: max(1, len(_words(question.choices.get(letter, "")))) for letter in LETTERS}
    correct_length = lengths.get(question.correct_key, 1)
    distractor_lengths = [length for letter, length in lengths.items() if letter != question.correct_key]
    flags: list[str] = []
    longest_distractor = max(distractor_lengths, default=correct_length)
    shortest_distractor = min(distractor_lengths, default=correct_length)
    if (
        correct_length > longest_distractor
        and correct_length - longest_distractor >= 2
        and correct_length / max(1, longest_distractor) >= 1.25
    ):
        flags.append("correct_choice_materially_longer_than_every_distractor")
    if (
        correct_length < shortest_distractor
        and shortest_distractor - correct_length >= 2
        and shortest_distractor / max(1, correct_length) >= 1.50
    ):
        flags.append("correct_choice_materially_shorter_than_every_distractor")
    return flags


def answer_length_leakage_summary(questions: Iterable[QuestionItem]) -> dict[str, float | int]:
    """Summarize how well a longest-choice guessing strategy would perform."""

    items = list(questions)
    among_longest = 0
    unique_longest = 0
    expected_score = 0.0
    materially_flagged = 0
    for question in items:
        lengths = {letter: max(1, len(_words(question.choices.get(letter, "")))) for letter in LETTERS}
        maximum = max(lengths.values(), default=0)
        winners = [letter for letter, length in lengths.items() if length == maximum]
        if question.correct_key in winners:
            among_longest += 1
            expected_score += 1.0 / max(1, len(winners))
            if len(winners) == 1:
                unique_longest += 1
        if choice_length_leakage_flags(question):
            materially_flagged += 1
    total = len(items)
    return {
        "questions": total,
        "correct_among_longest": among_longest,
        "correct_unique_longest": unique_longest,
        "materially_flagged": materially_flagged,
        "longest_strategy_expected_rate": expected_score / total if total else 0.0,
    }


def _cyrillic_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        return 0.0
    return sum(bool(re.fullmatch(r"[А-Яа-яЁё]", char)) for char in letters) / len(letters)


def _han_ratio(text: str) -> float:
    relevant = re.findall(r"[A-Za-zА-Яа-яЁё\u3400-\u9fff]", text)
    if not relevant:
        return 0.0
    return sum(bool(re.fullmatch(r"[\u3400-\u9fff]", char)) for char in relevant) / len(relevant)


def target_language_ratio(text: str, language: str) -> float:
    return _han_ratio(text) if language == "zh-CN" else _cyrillic_ratio(text)


def target_unit_count(text: str, language: str) -> int:
    if language == "zh-CN":
        return len(re.findall(r"[\u3400-\u9fff]", text))
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)?", text))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…。！？])\s*", text.strip()) if part.strip()]


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
        choice_near_duplicate(choices[i], choices[j])
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
    exact_word_count = target_unit_count(passage.passage_ru, passage.language)
    reading_limit = 1000 if passage.language == "zh-CN" else 500
    listening_limit = 750 if passage.language == "zh-CN" else 390
    reading_limit_ok = passage.skill != "reading" or exact_word_count <= reading_limit
    listening_limit_ok = passage.skill != "listening" or exact_word_count <= listening_limit
    target_ratio_ok = target_language_ratio(passage.passage_ru, passage.language) >= 0.65

    checks = {
        "passage_present": bool(passage.passage_ru.strip()),
        # Retained for backward compatibility with existing reports/tests; the
        # check now means "predominantly the passage's declared language."
        "passage_is_predominantly_russian": target_ratio_ok,
        "passage_is_predominantly_target_language": target_ratio_ok,
        "orientation_present": len(passage.orientation_en.strip()) >= 10,
        "orientation_is_primarily_english": (
            _cyrillic_ratio(passage.orientation_en) < 0.25
            and _han_ratio(passage.orientation_en) < 0.25
        ),
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
