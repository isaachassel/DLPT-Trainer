from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .constants import ILR_LEVELS, ILR_THETA
from .models import AbilityEstimate, AdaptiveSelection, PassageItem, QuestionItem, ResponseRecord

GRID = [round(-3.5 + i * 0.05, 2) for i in range(141)]


def logistic(theta: float, b: float, a: float = 1.0) -> float:
    z = max(-35.0, min(35.0, a * (theta - b)))
    return 1.0 / (1.0 + math.exp(-z))


def normal_density(x: float, mean: float, sd: float) -> float:
    variance = sd * sd
    return math.exp(-((x - mean) ** 2) / (2 * variance)) / math.sqrt(2 * math.pi * variance)


def initialize_ability(skill: str, prior_level: str | None = None, broad: bool = True) -> AbilityEstimate:
    mean = ILR_THETA.get(prior_level or "1+", ILR_THETA["1+"])
    sd = 1.20 if broad else 0.85
    weights = [normal_density(theta, mean, sd) for theta in GRID]
    total = sum(weights)
    weights = [w / total for w in weights]
    estimate = AbilityEstimate(skill=skill, posterior_grid=GRID.copy(), posterior_weights=weights)
    return summarize_posterior(estimate)


def _weighted_quantile(grid: list[float], weights: list[float], q: float) -> float:
    running = 0.0
    for theta, weight in zip(grid, weights):
        running += weight
        if running >= q:
            return theta
    return grid[-1]


def theta_to_practice_ilr(theta: float, predicted_success: dict[str, float], items_answered: int, se: float) -> str | None:
    if items_answered < 8 or se > 0.85:
        return None
    supported = "0"
    for level in ILR_LEVELS:
        if predicted_success.get(level, 0.0) >= 0.67:
            supported = level
    return supported


def summarize_posterior(estimate: AbilityEstimate) -> AbilityEstimate:
    grid = estimate.posterior_grid or GRID.copy()
    weights = estimate.posterior_weights
    if not weights:
        weights = [1 / len(grid)] * len(grid)
    total = sum(weights) or 1.0
    weights = [w / total for w in weights]
    mean = sum(theta * weight for theta, weight in zip(grid, weights))
    variance = sum(((theta - mean) ** 2) * weight for theta, weight in zip(grid, weights))
    se = math.sqrt(max(variance, 1e-9))
    predicted = {level: logistic(mean, difficulty) for level, difficulty in ILR_THETA.items()}
    practice_ilr = theta_to_practice_ilr(mean, predicted, estimate.items_answered, se)
    if estimate.items_answered < 8:
        confidence = "insufficient"
    elif se <= 0.35:
        confidence = "high"
    elif se <= 0.55:
        confidence = "moderate"
    else:
        confidence = "low"
    stable = estimate.items_answered >= 12 and se <= 0.55
    return estimate.model_copy(update={
        "theta": mean,
        "standard_error": se,
        "ci_low": _weighted_quantile(grid, weights, 0.10),
        "ci_high": _weighted_quantile(grid, weights, 0.90),
        "posterior_grid": grid,
        "posterior_weights": weights,
        "practice_ilr": practice_ilr,
        "confidence": confidence,
        "stable": stable,
        "predicted_success": predicted,
    })


def update_ability(estimate: AbilityEstimate, responses: Iterable[ResponseRecord]) -> AbilityEstimate:
    grid = estimate.posterior_grid or GRID.copy()
    weights = estimate.posterior_weights or [1 / len(grid)] * len(grid)
    correct_added = 0
    count_added = 0
    for response in responses:
        count_added += 1
        correct_added += int(response.is_correct)
        new_weights = []
        for theta, prior in zip(grid, weights):
            p = logistic(theta, response.item_difficulty, 1.0)
            likelihood = p if response.is_correct else (1.0 - p)
            new_weights.append(prior * max(likelihood, 1e-12))
        total = sum(new_weights)
        weights = [w / total for w in new_weights] if total else [1 / len(grid)] * len(grid)
    updated = estimate.model_copy(update={
        "posterior_grid": grid,
        "posterior_weights": weights,
        "items_answered": estimate.items_answered + count_added,
        "correct": estimate.correct + correct_added,
    })
    return summarize_posterior(updated)


def item_information(theta: float, difficulty: float, discrimination: float = 1.0) -> float:
    p = logistic(theta, difficulty, discrimination)
    return discrimination * discrimination * p * (1.0 - p)


def should_stop_diagnostic(estimate: AbilityEstimate, minimum: int, maximum: int) -> bool:
    if estimate.items_answered >= maximum:
        return True
    return estimate.items_answered >= minimum and estimate.standard_error <= 0.45


def _balance_penalty(value: str, exposure: Counter[str]) -> float:
    if not exposure:
        return 0.0
    minimum = min(exposure.values(), default=0)
    return max(0, exposure.get(value, 0) - minimum) * 0.16


def score_passage(
    passage: PassageItem,
    questions: list[QuestionItem],
    estimate: AbilityEstimate,
    mode: str,
    target_level: str,
    topic_exposure: Counter[str],
    genre_exposure: Counter[str],
    question_type_exposure: Counter[str],
    item_exposure: Counter[str],
) -> AdaptiveSelection:
    information = sum(item_information(estimate.theta, q.operational_difficulty, q.discrimination) for q in questions)
    mean_b = sum(q.operational_difficulty for q in questions) / max(1, len(questions))
    distance = abs(estimate.theta - mean_b)
    target_bias = 0.0
    if mode == "training":
        target_b = ILR_THETA[target_level]
        target_bias = max(0.0, 0.65 - abs(mean_b - target_b) * 0.25)
    qtype_penalty = sum(_balance_penalty(q.question_type, question_type_exposure) for q in questions) / max(1, len(questions))
    balance_penalty = (
        _balance_penalty(passage.topic, topic_exposure)
        + _balance_penalty(passage.genre, genre_exposure)
        + qtype_penalty
    )
    exposure_penalty = passage.exposure_count * 0.03 + item_exposure.get(passage.id, 0) * 0.45
    calibration_bonus = 0.10 if passage.calibrated_difficulty is not None else 0.0
    score = information * 2.2 - distance * 0.30 + target_bias + calibration_bonus - balance_penalty - exposure_penalty
    return AdaptiveSelection(
        passage_id=passage.id,
        skill=passage.skill,
        score=score,
        information=information,
        ability_distance=distance,
        target_bias=target_bias,
        balance_penalty=balance_penalty,
        exposure_penalty=exposure_penalty,
        reasons=[
            f"information={information:.3f}",
            f"distance={distance:.3f}",
            f"content_penalty={balance_penalty:.3f}",
            f"exposure_penalty={exposure_penalty:.3f}",
        ],
    )


def select_passage(
    passages: list[PassageItem],
    questions_by_passage: dict[str, list[QuestionItem]],
    estimate: AbilityEstimate,
    mode: str,
    target_level: str,
    seen_passages: set[str],
    seen_questions: set[str],
    topic_exposure: dict[str, int],
    genre_exposure: dict[str, int],
    question_type_exposure: dict[str, int],
    item_exposure: dict[str, int],
    allowed_topics: set[str] | None = None,
    preferred_competencies: set[str] | None = None,
    first_passage: bool = False,
) -> AdaptiveSelection:
    topic_counts = Counter(topic_exposure)
    genre_counts = Counter(genre_exposure)
    qtype_counts = Counter(question_type_exposure)
    item_counts = Counter(item_exposure)
    candidates: list[AdaptiveSelection] = []
    for passage in passages:
        if passage.id in seen_passages or passage.status != "active" or passage.validation_status != "accepted":
            continue
        if allowed_topics and passage.topic not in allowed_topics:
            continue
        questions = questions_by_passage.get(passage.id, [])
        if not questions or any(q.id in seen_questions for q in questions):
            continue
        if any(q.status != "active" or q.validation_status != "accepted" for q in questions):
            continue
        if first_passage and mode in {"diagnostic", "simulation"} and not (-0.65 <= passage.operational_difficulty <= 0.75):
            continue
        selection = score_passage(
            passage, questions, estimate, mode, target_level,
            topic_counts, genre_counts, qtype_counts, item_counts,
        )
        if preferred_competencies:
            matches = sum(q.question_type in preferred_competencies for q in questions)
            selection.score += 0.18 * matches
            if matches:
                selection.reasons.append(f"preferred_competency_matches={matches}")
        candidates.append(selection)
    if not candidates and allowed_topics:
        return select_passage(
            passages, questions_by_passage, estimate, mode, target_level,
            seen_passages, seen_questions, topic_exposure, genre_exposure,
            question_type_exposure, item_exposure, None, preferred_competencies, first_passage,
        )
    if not candidates:
        raise LookupError("No validated unseen passage is available for the requested skill and constraints.")
    candidates.sort(key=lambda item: (item.score, item.information), reverse=True)
    return candidates[0]
