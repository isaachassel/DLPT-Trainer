from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .schema import AnswerRecord, ILR_LEVELS


def get_level_decision(current_level: str, block_score: float, recent_scores: List[float]) -> Tuple[str, str]:
    """Return the next ILR level and a plain-English adaptive decision note."""
    idx = ILR_LEVELS.index(current_level)
    pct = int(round(block_score * 100))

    if block_score >= 1.0 and len(recent_scores) >= 1 and recent_scores[-1] >= 0.75:
        next_level = ILR_LEVELS[min(idx + 1, len(ILR_LEVELS) - 1)]
        if next_level != current_level:
            return next_level, f"Adaptive update: last block {pct}%. You performed strongly across two blocks, so the next block moved from ILR {current_level} to ILR {next_level}."
        return next_level, f"Adaptive update: last block {pct}%. You are already at the highest level available in this MVP, so the level stayed at ILR {current_level}."

    if block_score <= 0.25 and len(recent_scores) >= 1 and recent_scores[-1] <= 0.25:
        next_level = ILR_LEVELS[max(idx - 1, 0)]
        if next_level != current_level:
            return next_level, f"Adaptive update: last block {pct}%. Two weak blocks in a row, so the next block moved from ILR {current_level} to ILR {next_level}."
        return next_level, f"Adaptive update: last block {pct}%. You are already at the lowest level available, so the level stayed at ILR {current_level}."

    if block_score >= 0.75:
        return current_level, f"Adaptive update: last block {pct}%. Strong performance. One more strong block can move you up. Current level stays ILR {current_level}."

    if block_score >= 0.50:
        return current_level, f"Adaptive update: last block {pct}%. Mixed performance. The app is holding you at ILR {current_level} to collect more evidence."

    return current_level, f"Adaptive update: last block {pct}%. Weak block. If this repeats, the app will move you down one half-level. Current level stays ILR {current_level}."


def move_level(current_level: str, block_score: float, recent_scores: List[float]) -> str:
    return get_level_decision(current_level, block_score, recent_scores)[0]


def estimate_level(records: List[AnswerRecord], starting_level: str) -> str:
    if not records:
        return starting_level

    by_level: Dict[str, List[bool]] = defaultdict(list)
    for r in records:
        by_level[r.ilr_level].append(r.is_correct)

    best_supported = starting_level
    for level in ILR_LEVELS:
        values = by_level.get(level, [])
        if len(values) >= 4 and sum(values) / len(values) >= 0.70:
            best_supported = level
    return best_supported


def summarize_records(records: List[AnswerRecord], starting_level: str, planned_questions: int | None = None) -> Tuple[str, str]:
    if not records:
        return starting_level, "No completed questions yet."

    total = len(records)
    correct = sum(1 for r in records if r.is_correct)
    accuracy = correct / total if total else 0
    estimated = estimate_level(records, starting_level)

    by_type = defaultdict(lambda: [0, 0])
    by_level = defaultdict(lambda: [0, 0])
    for r in records:
        by_type[r.question.question_type][1] += 1
        by_level[r.ilr_level][1] += 1
        if r.is_correct:
            by_type[r.question.question_type][0] += 1
            by_level[r.ilr_level][0] += 1

    weak_types = []
    for qtype, (c, n) in by_type.items():
        if n >= 2 and c / n < 0.70:
            weak_types.append(f"{qtype} ({c}/{n})")

    lines = []
    header = "## Current Report" if planned_questions and total >= planned_questions else "## Final Report"
    lines.append(header)
    lines.append(f"**Estimated Reading Level:** ILR {estimated}")
    lines.append(f"**Overall Accuracy:** {correct}/{total} ({accuracy:.0%})")
    if planned_questions:
        lines.append(f"**Current Session Progress:** {total}/{planned_questions} questions")
    lines.append("")
    lines.append("### Accuracy by ILR Level")
    for level in ILR_LEVELS:
        if level in by_level:
            c, n = by_level[level]
            lines.append(f"- ILR {level}: {c}/{n} ({c/n:.0%})")
    lines.append("")
    lines.append("### Adaptive Path")
    path = []
    for r in records:
        label = f"Block {r.block_number}: ILR {r.ilr_level}"
        if label not in path:
            path.append(label)
    for item in path:
        lines.append(f"- {item}")
    lines.append("")
    if weak_types:
        lines.append("### Main Weak Areas")
        for item in weak_types:
            lines.append(f"- {item}")
    else:
        lines.append("### Main Weak Areas")
        lines.append("- No clear weakness detected in this short session.")
    lines.append("")
    lines.append("### Missed Questions Review")
    missed = [r for r in records if not r.is_correct]
    if not missed:
        lines.append("No missed questions. Increase the starting level next session.")
    else:
        for i, r in enumerate(missed, start=1):
            selected = r.selected_answer or "No answer"
            lines.append(f"\n**Missed Question {i} — ILR {r.ilr_level}, {r.question.question_type}**")
            lines.append(f"**Question:** {r.question.question}")
            lines.append(f"**Your answer:** {selected}")
            lines.append(f"**Correct answer:** {r.question.correct_answer}. {r.question.choices[r.question.correct_answer]}")
            lines.append(f"**Why:** {r.question.explanation}")
            lines.append(f"**Evidence:** {r.question.evidence}")
    lines.append("")
    lines.append("### Recommended Next Session")
    if weak_types:
        lines.append(f"Continue at ILR {estimated} and practice the weakest question types above.")
    else:
        lines.append(f"Continue at ILR {estimated} or one half-level higher if this felt too easy.")

    return estimated, "\n".join(lines)
