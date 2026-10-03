"""Provisional Bayesian passage-testlet assessment; see docs/ADAPTIVE_ASSESSMENT.md.

No empirical item parameters or official DLPT/ODA scoring are assumed.
"""
from __future__ import annotations

import math

from .adaptive import _weighted_quantile, ilr_range, nearest_ilr, normal_density, response_probability
from .constants import ILR_LEVELS, ILR_THETA
from .models import AbilityEstimate, SessionState
from .validation import content_hash

GRID = [round(-5 + i * 0.05, 2) for i in range(201)]
OFFSETS = [i * 0.25 for i in range(-12, 13)]
_density = [normal_density(offset, 0, 0.75) for offset in OFFSETS]
OFFSET_WEIGHTS = [weight / sum(_density) for weight in _density]

END_REASONS = {
    "precision": "The minimum length and uncertainty target were met, with evidence from at least two difficulty bands.",
    "maximum": "The maximum number of passages was reached.",
    "content_exhausted": "Insufficient content: no eligible unseen passages remain for this skill and language.",
    "abandoned": "The assessment was ended by the learner before completion.",
}


def summarize(estimate: AbilityEstimate) -> AbilityEstimate:
    grid, weights = estimate.posterior_grid, estimate.posterior_weights
    mean = sum(x * w for x, w in zip(grid, weights))
    sd = math.sqrt(sum(w * (x - mean) ** 2 for x, w in zip(grid, weights)))
    return estimate.model_copy(update={
        "theta": mean, "standard_error": sd,
        "ci_low": _weighted_quantile(grid, weights, 0.05),
        "ci_high": _weighted_quantile(grid, weights, 0.95),
        "practice_ilr": nearest_ilr(mean) if estimate.items_answered else None,
        "routing_ilr": nearest_ilr(mean),
        "confidence": "low", "stable": False,
    })


def initialize(skill: str) -> AbilityEstimate:
    weights = [normal_density(x, ILR_THETA["1+"], 1.5) for x in GRID]
    total = sum(weights)
    return summarize(AbilityEstimate(skill=skill, posterior_grid=GRID.copy(),
                                     posterior_weights=[w / total for w in weights]))


def update(estimate: AbilityEstimate, records) -> AbilityEstimate:
    """One atomic passage update, integrating out its shared difficulty offset."""
    records = list(records)
    if not records or len({r.passage_id for r in records}) != 1:
        raise ValueError("Assessment updates require exactly one complete passage")
    if any(r.skill != estimate.skill for r in records):
        raise ValueError("Reading and listening evidence must remain separate")
    weights = []
    for theta, prior in zip(estimate.posterior_grid, estimate.posterior_weights):
        likelihood = 0.0
        for offset, offset_weight in zip(OFFSETS, OFFSET_WEIGHTS):
            conditional = 1.0
            for record in records:
                p = response_probability(theta, ILR_THETA[record.target_ilr] + offset,
                                         guessing=1 / len(record.choices_snapshot))
                conditional *= p if record.is_correct else 1 - p
            likelihood += offset_weight * conditional
        weights.append(prior * max(likelihood, 1e-15))
    total = sum(weights)
    evidence = dict(estimate.evidence_by_ilr)
    for record in records:
        evidence[record.target_ilr] = evidence.get(record.target_ilr, 0) + 1
    return summarize(estimate.model_copy(update={
        "posterior_weights": [w / total for w in weights],
        "items_answered": estimate.items_answered + len(records),
        "correct": estimate.correct + sum(r.is_correct for r in records),
        "evidence_by_ilr": evidence,
    }))


def passage_count(state: SessionState, skill: str) -> int:
    return len({record.passage_id for record in state.responses_for(skill)})


def precision_met(state: SessionState, skill: str) -> bool:
    estimate = state.ability_for(skill)
    return (passage_count(state, skill) >= state.assessment_min_passages
            and estimate.standard_error <= state.assessment_target_sd
            and len(estimate.evidence_by_ilr) >= 2)


def stop_reason(state: SessionState, skill: str) -> str | None:
    # A hard maximum always wins, including when precision is met simultaneously.
    if passage_count(state, skill) >= state.assessment_max_passages:
        return "maximum"
    if precision_met(state, skill):
        return "precision"
    return None


def band_probabilities(estimate: AbilityEstimate) -> dict[str, float]:
    probabilities = dict.fromkeys(ILR_LEVELS, 0.0)
    for theta, weight in zip(estimate.posterior_grid, estimate.posterior_weights):
        probabilities[nearest_ilr(theta)] += weight
    return probabilities


def select(state: SessionState, bank, history=None):
    """Select the nearest provisional band, balancing topics within that band.

    Bank validation enforces skill, language, question validity and linked audio.
    Text hashes also prevent a duplicate passage under a different ID.
    """
    seen = set(state.completed_passage_ids)
    if history:
        seen.update(history.seen_passage_ids)
    hashes = {content_hash(bank.passages[pid].passage_ru) for pid in seen if pid in bank.passages}
    allowed = set(ilr_range(state.minimum_ilr, state.maximum_ilr))
    candidates = []
    for passage in bank.active_passages(state.active_skill, state.language):
        questions = bank.get_questions(passage.id)
        if passage.id in seen or content_hash(passage.passage_ru) in hashes or not questions:
            continue
        if not {q.target_ilr for q in questions}.issubset(allowed):
            continue
        if any(q.id in state.completed_question_ids for q in questions):
            continue
        candidates.append((passage, questions))
    if not candidates:
        raise LookupError(END_REASONS["content_exhausted"])
    theta = state.ability_for(state.active_skill).theta
    def rank(pair):
        passage, questions = pair
        difficulty = sum(ILR_THETA[q.target_ilr] for q in questions) / len(questions)
        topic_penalty = int(bool(state.topics) and passage.topic not in state.topics)
        competency_matches = sum(q.question_type in state.competencies for q in questions)
        return (abs(theta - difficulty), topic_penalty, -competency_matches,
                state.topic_exposure.get(passage.topic, 0), passage.id)
    return min(candidates, key=rank)
