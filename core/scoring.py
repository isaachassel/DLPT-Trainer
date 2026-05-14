from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from .schema import AnswerRecord, ILR_LEVELS, SessionState


def move_level(current_level: str, block_score: float, recent_scores: List[float]) -> str:
    idx = ILR_LEVELS.index(current_level)

    if block_score >= 1.0 and len(recent_scores) >= 1 and recent_scores[-1] >= 0.75:
        return ILR_LEVELS[min(idx + 1, len(ILR_LEVELS) - 1)]

    if block_score <= 0.25 and len(recent_scores) >= 1 and recent_scores[-1] <= 0.25:
        return ILR_LEVELS[max(idx - 1, 0)]

    return current_level


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


def summarize_records(records: List[AnswerRecord], starting_level: str) -> Tuple[str, str]:
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
    lines.append(f"## Final Report")
    lines.append(f"**Estimated Reading Level:** ILR {estimated}")
    lines.append(f"**Overall Accuracy:** {correct}/{total} ({accuracy:.0%})")
    lines.append("")
    lines.append("### Accuracy by ILR Level")
    for level in ILR_LEVELS:
        if level in by_level:
            c, n = by_level[level]
            lines.append(f"- ILR {level}: {c}/{n} ({c/n:.0%})")
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
        lines.append(f"Start at ILR {estimated} and practice the weakest question types above.")
    else:
        lines.append(f"Start at ILR {estimated} or one half-level higher if this felt too easy.")

    return estimated, "\n".join(lines)
