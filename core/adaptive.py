from __future__ import annotations

import math
import random
from collections import Counter
from typing import Iterable

from .constants import ILR_LEVELS, ILR_THETA
from .models import AbilityEstimate, AdaptiveSelection, PassageItem, QuestionItem, ResponseRecord

GRID = [round(-3.5 + i * 0.05, 2) for i in range(141)]
# The passage-level likelihood discount below intentionally preserves more
# uncertainty than an item-independent model. A 0.56 routing boundary still
# requires sustained posterior evidence, while allowing an entirely missed
# multi-question passage to move delivery down one adjacent half-level.
ROUTING_POSTERIOR_THRESHOLD = 0.56
MULTIPLE_CHOICE_GUESSING = 0.25


def logistic(theta: float, b: float, a: float = 1.0) -> float:
    z = max(-35.0, min(35.0, a * (theta - b)))
    return 1.0 / (1.0 + math.exp(-z))


def response_probability(
    theta: float,
    b: float,
    a: float = 1.0,
    guessing: float = MULTIPLE_CHOICE_GUESSING,
) -> float:
    """Chance-aware response probability for four-option practice items.

    The bank is not empirically calibrated, so the 0.25 lower asymptote is a
    transparent structural correction rather than a fitted item parameter.
    """

    guessing = max(0.0, min(0.45, guessing))
    return guessing + (1.0 - guessing) * logistic(theta, b, a)


def normal_density(x: float, mean: float, sd: float) -> float:
    variance = sd * sd
    return math.exp(-((x - mean) ** 2) / (2 * variance)) / math.sqrt(2 * math.pi * variance)


def nearest_ilr(theta: float) -> str:
    return min(ILR_LEVELS, key=lambda level: abs(ILR_THETA[level] - theta))


def clamp_ilr(level: str, minimum_ilr: str = "0", maximum_ilr: str = "3") -> str:
    low = ILR_LEVELS.index(minimum_ilr)
    high = ILR_LEVELS.index(maximum_ilr)
    index = ILR_LEVELS.index(level)
    return ILR_LEVELS[max(low, min(high, index))]


def ilr_range(minimum_ilr: str = "0", maximum_ilr: str = "3") -> list[str]:
    low = ILR_LEVELS.index(minimum_ilr)
    high = ILR_LEVELS.index(maximum_ilr)
    if low > high:
        raise ValueError("minimum_ilr cannot be higher than maximum_ilr")
    return ILR_LEVELS[low : high + 1]


def operational_ilr(question: QuestionItem) -> str:
    """Return the best available operational band for bank eligibility and routing.

    Empirically calibrated difficulty overrides the authoring target. Until then,
    the validated authoring target remains provisional metadata.
    """

    if question.calibrated_difficulty is not None:
        return nearest_ilr(question.calibrated_difficulty)
    return question.target_ilr


def initialize_ability(
    skill: str,
    prior_level: str | None = None,
    broad: bool = True,
    routing_level: str | None = None,
) -> AbilityEstimate:
    prior = prior_level or "1+"
    mean = ILR_THETA.get(prior, ILR_THETA["1+"])
    sd = 1.20 if broad else 0.85
    weights = [normal_density(theta, mean, sd) for theta in GRID]
    total = sum(weights)
    weights = [w / total for w in weights]
    estimate = AbilityEstimate(
        skill=skill,
        posterior_grid=GRID.copy(),
        posterior_weights=weights,
        routing_ilr=routing_level or prior,
    )
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
    # A 67%-at-anchor rule systematically reports a learner about one full
    # theta unit below the posterior center. A nearest-anchor classification is
    # symmetric around the provisional ILR anchors and is therefore the more
    # honest display for an explicitly provisional working band.
    return nearest_ilr(theta)


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
    predicted = {level: response_probability(mean, difficulty) for level, difficulty in ILR_THETA.items()}
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
    records = list(responses)
    grid = estimate.posterior_grid or GRID.copy()
    weights = estimate.posterior_weights or [1 / len(grid)] * len(grid)
    correct_added = 0
    count_added = 0
    evidence_by_ilr = dict(estimate.evidence_by_ilr)
    correct_by_ilr = dict(estimate.correct_by_ilr)
    passage_counts = Counter(record.passage_id for record in records)
    for response in records:
        count_added += 1
        correct_added += int(response.is_correct)
        evidence_by_ilr[response.target_ilr] = evidence_by_ilr.get(response.target_ilr, 0) + 1
        if response.is_correct:
            correct_by_ilr[response.target_ilr] = correct_by_ilr.get(response.target_ilr, 0) + 1
        new_weights = []
        for theta, prior in zip(grid, weights):
            p = response_probability(theta, response.item_difficulty, response.item_discrimination)
            likelihood = p if response.is_correct else (1.0 - p)
            # Questions attached to one passage share source comprehension and
            # are not fully independent. Discount each likelihood by the square
            # root of its passage testlet size so confidence does not collapse
            # unrealistically after one multi-question passage.
            testlet_weight = 1.0 / math.sqrt(max(1, passage_counts[response.passage_id]))
            new_weights.append(prior * max(likelihood, 1e-12) ** testlet_weight)
        total = sum(new_weights)
        weights = [w / total for w in new_weights] if total else [1 / len(grid)] * len(grid)
    updated = estimate.model_copy(update={
        "posterior_grid": grid,
        "posterior_weights": weights,
        "items_answered": estimate.items_answered + count_added,
        "correct": estimate.correct + correct_added,
        "evidence_by_ilr": evidence_by_ilr,
        "correct_by_ilr": correct_by_ilr,
    })
    return summarize_posterior(updated)


def _posterior_probability(estimate: AbilityEstimate, *, below: float | None = None, above: float | None = None) -> float:
    probability = 0.0
    for theta, weight in zip(estimate.posterior_grid, estimate.posterior_weights):
        if below is not None and theta < below:
            probability += weight
        elif above is not None and theta > above:
            probability += weight
    return probability


def update_routing_band(
    estimate: AbilityEstimate,
    responses: Iterable[ResponseRecord],
    minimum_ilr: str = "0",
    maximum_ilr: str = "3",
    threshold: float = ROUTING_POSTERIOR_THRESHOLD,
) -> AbilityEstimate:
    """Update the passage-routing band from the Bayesian posterior.

    The posterior remains continuous. The routing band is a conservative delivery
    guard that moves at most one ILR half-step after a passage, preventing a
    single response from causing a large jump while still allowing sustained
    evidence to move the test up or down.
    """

    records = list(responses)
    current = clamp_ilr(estimate.routing_ilr, minimum_ilr, maximum_ilr)
    current_index = ILR_LEVELS.index(current)
    low_index = ILR_LEVELS.index(minimum_ilr)
    high_index = ILR_LEVELS.index(maximum_ilr)
    next_band = current
    direction_probability = 0.0
    reason = "posterior evidence did not cross the adjacent-band routing threshold"

    if current_index > low_index:
        lower = ILR_LEVELS[current_index - 1]
        lower_midpoint = (ILR_THETA[lower] + ILR_THETA[current]) / 2.0
        probability_below = _posterior_probability(estimate, below=lower_midpoint)
    else:
        probability_below = 0.0

    if current_index < high_index:
        upper = ILR_LEVELS[current_index + 1]
        upper_midpoint = (ILR_THETA[current] + ILR_THETA[upper]) / 2.0
        probability_above = _posterior_probability(estimate, above=upper_midpoint)
    else:
        probability_above = 0.0

    # Only one adjacent half-level move is allowed per completed passage. A
    # single question is not enough evidence for a routing transition.
    bundle_has_multiple_items = len(records) >= 2
    if (
        bundle_has_multiple_items
        and probability_below >= threshold
        and probability_below > probability_above
        and current_index > low_index
    ):
        next_band = ILR_LEVELS[current_index - 1]
        direction_probability = probability_below
        reason = f"{probability_below:.0%} posterior probability below the {next_band}/{current} boundary"
    elif bundle_has_multiple_items and probability_above >= threshold and current_index < high_index:
        next_band = ILR_LEVELS[current_index + 1]
        direction_probability = probability_above
        reason = f"{probability_above:.0%} posterior probability above the {current}/{next_band} boundary"

    correct = sum(int(record.is_correct) for record in records)
    event = {
        "after_items": estimate.items_answered,
        "from_ilr": current,
        "to_ilr": next_band,
        "posterior_theta": round(estimate.theta, 4),
        "posterior_standard_error": round(estimate.standard_error, 4),
        "probability_below": round(probability_below, 4),
        "probability_above": round(probability_above, 4),
        "direction_probability": round(direction_probability, 4),
        "bundle_correct": correct,
        "bundle_total": len(records),
        "reason": reason,
    }
    history = [*estimate.routing_history, event]
    return estimate.model_copy(update={"routing_ilr": next_band, "routing_history": history})


def item_information(
    theta: float,
    difficulty: float,
    discrimination: float = 1.0,
    guessing: float = MULTIPLE_CHOICE_GUESSING,
) -> float:
    logistic_part = logistic(theta, difficulty, discrimination)
    p = guessing + (1.0 - guessing) * logistic_part
    derivative = discrimination * (1.0 - guessing) * logistic_part * (1.0 - logistic_part)
    return (derivative * derivative) / max(1e-9, p * (1.0 - p))


def adjacent_evidence_ready(
    estimate: AbilityEstimate,
    minimum_ilr: str = "0",
    maximum_ilr: str = "3",
    minimum_items_per_band: int = 2,
) -> bool:
    current = clamp_ilr(estimate.routing_ilr, minimum_ilr, maximum_ilr)
    current_index = ILR_LEVELS.index(current)
    low_index = ILR_LEVELS.index(minimum_ilr)
    high_index = ILR_LEVELS.index(maximum_ilr)
    if estimate.evidence_by_ilr.get(current, 0) < minimum_items_per_band:
        return False
    neighbors: list[str] = []
    if current_index > low_index:
        neighbors.append(ILR_LEVELS[current_index - 1])
    if current_index < high_index:
        neighbors.append(ILR_LEVELS[current_index + 1])
    if not neighbors:
        return True
    return any(estimate.evidence_by_ilr.get(level, 0) >= minimum_items_per_band for level in neighbors)


def diagnostic_probe_band(
    estimate: AbilityEstimate,
    minimum_ilr: str = "0",
    maximum_ilr: str = "3",
    minimum_items_per_band: int = 2,
) -> str:
    """Choose an adjacent boundary-probe band when diagnostic evidence is thin."""

    current = clamp_ilr(estimate.routing_ilr, minimum_ilr, maximum_ilr)
    if estimate.evidence_by_ilr.get(current, 0) < minimum_items_per_band:
        return current
    current_index = ILR_LEVELS.index(current)
    low_index = ILR_LEVELS.index(minimum_ilr)
    high_index = ILR_LEVELS.index(maximum_ilr)
    neighbors: list[str] = []
    if current_index > low_index:
        neighbors.append(ILR_LEVELS[current_index - 1])
    if current_index < high_index:
        neighbors.append(ILR_LEVELS[current_index + 1])
    under_sampled = [level for level in neighbors if estimate.evidence_by_ilr.get(level, 0) < minimum_items_per_band]
    if not under_sampled:
        return current
    # Probe the adjacent boundary whose item difficulty is closest to the
    # posterior mean; this gives useful classification evidence with the least
    # unnecessary difficulty jump.
    return min(under_sampled, key=lambda level: abs(estimate.theta - ILR_THETA[level]))


def should_stop_diagnostic(
    estimate: AbilityEstimate,
    minimum: int,
    maximum: int,
    minimum_ilr: str = "0",
    maximum_ilr: str = "3",
) -> bool:
    if estimate.items_answered >= maximum:
        return True
    return (
        estimate.items_answered >= minimum
        and estimate.standard_error <= 0.45
        and adjacent_evidence_ready(estimate, minimum_ilr, maximum_ilr)
    )


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
    routing_band: str | None = None,
) -> AdaptiveSelection:
    raw_information = sum(item_information(estimate.theta, q.operational_difficulty, q.discrimination) for q in questions)
    # Passage bundles legitimately provide more evidence, but this normalization
    # prevents five-question passages from automatically dominating all shorter bundles.
    information = raw_information / math.sqrt(max(1, len(questions)))
    mean_b = sum(q.operational_difficulty for q in questions) / max(1, len(questions))
    distance = abs(estimate.theta - mean_b)
    selected_band = nearest_ilr(mean_b)
    route = routing_band or estimate.routing_ilr or nearest_ilr(estimate.theta)
    band_distance = abs(ILR_LEVELS.index(selected_band) - ILR_LEVELS.index(route))
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
    routing_penalty = band_distance * 0.42
    score = information * 2.2 - distance * 0.30 + target_bias + calibration_bonus - balance_penalty - exposure_penalty - routing_penalty
    return AdaptiveSelection(
        passage_id=passage.id,
        skill=passage.skill,
        score=score,
        information=information,
        ability_distance=distance,
        target_bias=target_bias,
        balance_penalty=balance_penalty,
        exposure_penalty=exposure_penalty,
        routing_band=route,
        selected_band=selected_band,
        band_distance=band_distance,
        reasons=[
            f"information={information:.3f}",
            f"distance={distance:.3f}",
            f"routing_band={route}",
            f"selected_band={selected_band}",
            f"band_distance={band_distance}",
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
    allowed_ilr_bands: set[str] | None = None,
    routing_band: str | None = None,
    selection_seed: str | None = None,
) -> AdaptiveSelection:
    topic_counts = Counter(topic_exposure)
    genre_counts = Counter(genre_exposure)
    qtype_counts = Counter(question_type_exposure)
    item_counts = Counter(item_exposure)
    route = routing_band or estimate.routing_ilr or nearest_ilr(estimate.theta)
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
        question_bands = {operational_ilr(question) for question in questions}
        if allowed_ilr_bands and not question_bands.issubset(allowed_ilr_bands):
            continue
        if (
            first_passage
            and mode in {"diagnostic", "simulation"}
            and route == "2"
            and not (-0.65 <= passage.operational_difficulty <= 0.75)
        ):
            continue
        selection = score_passage(
            passage, questions, estimate, mode, target_level,
            topic_counts, genre_counts, qtype_counts, item_counts, route,
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
            allowed_ilr_bands, route, selection_seed,
        )
    if not candidates:
        band_note = f" within ILR bands {sorted(allowed_ilr_bands, key=ILR_LEVELS.index)}" if allowed_ilr_bands else ""
        raise LookupError(f"No validated unseen passage is available for the requested skill and constraints{band_note}.")

    # Prefer the current routing band; if the bank has none, use the nearest
    # adjacent band rather than silently jumping across several levels.
    minimum_band_distance = min(item.band_distance for item in candidates)
    candidates = [item for item in candidates if item.band_distance == minimum_band_distance]
    candidates.sort(key=lambda item: (item.score, item.information), reverse=True)

    # Randomize deterministically among near-equivalent top candidates to reduce
    # systematic overexposure while preserving reproducibility and checkpoints.
    top_score = candidates[0].score
    top_pool = [item for item in candidates[:5] if item.score >= top_score - 0.12]
    if len(top_pool) == 1 or not selection_seed:
        return top_pool[0]
    return random.Random(selection_seed).choice(top_pool)
