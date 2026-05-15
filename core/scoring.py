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


def _block_scores(records: List[AnswerRecord]) -> List[Tuple[int, str, str, int, int]]:
    """Return block_number, ILR level, correct, total for each completed block."""
    by_block: Dict[int, List[AnswerRecord]] = defaultdict(list)
    for r in records:
        by_block[r.block_number].append(r)

    rows: List[Tuple[int, str, str, int, int]] = []
    for block_num in sorted(by_block):
        block_records = by_block[block_num]
        level = block_records[0].ilr_level if block_records else "?"
        skill = block_records[0].skill.title() if block_records else "?"
        correct = sum(1 for r in block_records if r.is_correct)
        rows.append((block_num, skill, level, correct, len(block_records)))
    return rows


def _missed_review(missed: List[AnswerRecord], heading: str, limit: int | None = None) -> str:
    lines: List[str] = [heading]
    if not missed:
        lines.append("No missed questions in this section.")
        return "\n".join(lines)

    items = missed if limit is None else missed[:limit]
    shown_transcripts = set()

    for i, r in enumerate(items, start=1):
        selected = r.selected_answer or "No answer"

        # For listening, show the transcript once per missed block instead of
        # repeating the same transcript under every missed question.
        transcript_key = (r.block_number, r.skill)
        if r.skill == "listening" and transcript_key not in shown_transcripts:
            shown_transcripts.add(transcript_key)
            lines.append(f"\n### Transcript for Block {r.block_number}")
            lines.append(r.passage_ru)

        lines.append(f"\n**Missed Question {i} — Block {r.block_number}, {r.skill.title()}, ILR {r.ilr_level}, {r.question.question_type}**")
        lines.append(f"**Question:** {r.question.question}")
        lines.append(f"**Your answer:** {selected}")
        lines.append(f"**Correct answer:** {r.question.correct_answer}. {r.question.choices[r.question.correct_answer]}")
        lines.append(f"**English explanation:** {r.question.explanation}")
        lines.append(f"**Evidence from Russian:** {r.question.evidence}")

    if limit is not None and len(missed) > limit:
        lines.append(f"\nShowing {limit} of {len(missed)} missed questions in this section.")
    return "\n".join(lines)

def summarize_records_sections(records: List[AnswerRecord], starting_level: str, planned_questions: int | None = None) -> Tuple[str, str, str, str]:
    """Return estimated level plus three UI-friendly report sections.

    Sections are split so the Gradio UI can place them in separate tabs:
    Summary, Latest Block Review, and All Missed Questions.
    """
    if not records:
        return starting_level, "No completed questions yet.", "No completed block yet.", "No missed questions yet."

    total = len(records)
    correct = sum(1 for r in records if r.is_correct)
    accuracy = correct / total if total else 0
    estimated = estimate_level(records, starting_level)
    skills = sorted(set(r.skill for r in records))
    skill_label = "Mixed" if len(skills) > 1 else skills[0].title()

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

    block_rows = _block_scores(records)
    latest_block = max(r.block_number for r in records)
    latest_records = [r for r in records if r.block_number == latest_block]
    latest_correct = sum(1 for r in latest_records if r.is_correct)
    latest_total = len(latest_records)
    latest_level = latest_records[0].ilr_level if latest_records else "?"
    latest_skill = latest_records[0].skill.title() if latest_records else "?"
    latest_missed = [r for r in latest_records if not r.is_correct]
    all_missed = [r for r in records if not r.is_correct]

    summary: List[str] = []
    summary.append(f"## Updated Cumulative Report ({total} completed questions)")
    if skill_label == "Mixed":
        # For mixed diagnostic, show simple separate estimates by skill when enough evidence exists.
        reading_records = [r for r in records if r.skill == "reading"]
        listening_records = [r for r in records if r.skill == "listening"]
        if reading_records:
            summary.append(f"**Estimated Reading Level:** ILR {estimate_level(reading_records, starting_level)}")
        if listening_records:
            summary.append(f"**Estimated Listening Level:** ILR {estimate_level(listening_records, starting_level)}")
    else:
        summary.append(f"**Estimated {skill_label} Level:** ILR {estimated}")
    summary.append(f"**Overall Accuracy:** {correct}/{total} ({accuracy:.0%})")
    if planned_questions:
        summary.append(f"**Current Session Progress:** {total}/{planned_questions} questions")
    summary.append(f"**Latest Completed Block:** Block {latest_block}, {latest_skill}, ILR {latest_level}, {latest_correct}/{latest_total} correct")
    summary.append("")

    summary.append("### Score by Block")
    for block_num, skill, level, c, n in block_rows:
        marker = " ← latest" if block_num == latest_block else ""
        summary.append(f"- Block {block_num} — {skill}, ILR {level}: {c}/{n} ({c/n:.0%}){marker}")
    summary.append("")

    summary.append("### Accuracy by ILR Level")
    for level in ILR_LEVELS:
        if level in by_level:
            c, n = by_level[level]
            summary.append(f"- ILR {level}: {c}/{n} ({c/n:.0%})")
    summary.append("")

    summary.append("### Adaptive Path")
    for block_num, skill, level, _c, _n in block_rows:
        summary.append(f"- Block {block_num}: {skill}, ILR {level}")
    summary.append("")

    summary.append("### Main Weak Areas")
    if weak_types:
        for item in weak_types:
            summary.append(f"- {item}")
    else:
        summary.append("- No clear weakness detected yet.")
    summary.append("")

    summary.append("### Recommended Next Session")
    if weak_types:
        summary.append(f"Continue at ILR {estimated} and practice the weakest question types above.")
    else:
        summary.append(f"Continue at ILR {estimated} or one half-level higher if this felt too easy.")

    latest_report = _missed_review(latest_missed, f"## Latest Block Review — Block {latest_block} ({latest_correct}/{latest_total})")
    missed_report = _missed_review(all_missed, f"## All Missed Questions Review ({len(all_missed)} missed of {total})")

    return estimated, "\n".join(summary), latest_report, missed_report


def summarize_records(records: List[AnswerRecord], starting_level: str, planned_questions: int | None = None) -> Tuple[str, str]:
    """Backward-compatible combined report."""
    estimated, summary, latest, missed = summarize_records_sections(records, starting_level, planned_questions)
    return estimated, "\n\n---\n\n".join([summary, latest, missed])
