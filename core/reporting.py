from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .item_bank import ItemBank
from .models import ResponseRecord, SessionState
from .scoring import accuracy, estimate_label, grouped_accuracy, item_level_label, response_time_summary, strengths_and_weaknesses
from .storage import export_responses_csv, export_session_json


def _format_group(title: str, grouped: dict[str, tuple[int, int, float]]) -> list[str]:
    lines = [f"### {title}"]
    if not grouped:
        return lines + ["No evidence."]
    for label, (correct, total, pct) in grouped.items():
        lines.append(f"- **{label}:** {correct}/{total} ({pct:.0%})")
    return lines



def _question_level_review(records: list[ResponseRecord]) -> list[str]:
    lines = [
        "### Question-level ILR review",
        (
            "Item levels were hidden during active Diagnostic and Full Simulation sections. "
            "A provisional level is an authoring and validation target, not an empirically calibrated fact."
        ),
    ]
    if not records:
        return lines + ["No completed questions."]
    passage_numbers: dict[str, int] = {}
    next_passage = 1
    for index, record in enumerate(records, start=1):
        if record.passage_id not in passage_numbers:
            passage_numbers[record.passage_id] = next_passage
            next_passage += 1
        result = "✅ Correct" if record.is_correct else "❌ Incorrect"
        lines.append(
            f"- **Q{index} · Passage {passage_numbers[record.passage_id]} · {result}:** "
            f"{item_level_label(record)} · {record.question_type} · {record.topic} / {record.genre}"
        )
    return lines

def _recommendation(records: list[ResponseRecord], estimate_level: str | None, weaknesses: list[str]) -> str:
    level = estimate_level or "the current working band"
    weak_text = ", ".join(weaknesses) if weaknesses else "mixed comprehension skills"
    genres = grouped_accuracy(records, "genre")
    lowest_genre = min(genres.items(), key=lambda x: x[1][2])[0] if genres else "mixed real-world texts"
    return (
        f"Next session: complete 12–16 questions near ILR {level}; emphasize {weak_text}; "
        f"include at least two {lowest_genre} passages; then retest one adjacent higher band only after accuracy stabilizes."
    )


def build_skill_report(state: SessionState, skill: str, bank: ItemBank, include_review: bool = True) -> str:
    records = state.responses_for(skill)
    estimate = state.ability_for(skill)
    correct, attempted, pct = accuracy(records)
    strongest, weakest = strengths_and_weaknesses(records)
    timing = response_time_summary(records)
    lines = [f"## {skill.title()} Practice Report", f"**{estimate_label(estimate)}**"]
    lines.append(f"Evidence: **{attempted} validated practice questions**, {correct} correct ({pct:.0%}).")
    lines.append(f"80% posterior interval (internal scale): **{estimate.ci_low:.2f} to {estimate.ci_high:.2f}**; standard error **{estimate.standard_error:.2f}**.")
    if state.shortened_simulation and state.mode == "simulation":
        lines.append("**This was a shortened simulation and is not equivalent to a complete test.**")
    lines.append("All uncalibrated bank and live-generated item difficulties are provisional rather than empirical psychometric parameters.")
    lines.extend(_format_group("Accuracy by ILR band", grouped_accuracy(records, "target_ilr")))
    lines.extend(_question_level_review(records))
    lines.extend(_format_group("Accuracy by question type", grouped_accuracy(records, "question_type")))
    lines.extend(_format_group("Accuracy by topic", grouped_accuracy(records, "topic")))
    lines.extend(_format_group("Accuracy by genre", grouped_accuracy(records, "genre")))
    lines.append("### Response-time patterns")
    lines.append(f"- Mean: {timing['mean']:.1f}s/question; median: {timing['median']:.1f}s; longest: {timing['max']:.1f}s.")
    if skill == "listening":
        plays = sum(record.listening_play_count for record in records)
        lines.append(f"- Recorded playback count across submitted items: {plays}.")
    lines.append("### Strongest competencies")
    lines.extend([f"- {value}" for value in strongest] or ["- Not enough balanced evidence yet."])
    lines.append("### Weakest competencies")
    lines.extend([f"- {value}" for value in weakest] or ["- Not enough balanced evidence yet."])
    lines.append("### Concrete next-session plan")
    lines.append(_recommendation(records, estimate.practice_ilr, weakest))
    if include_review:
        lines.append("### Missed-question review")
        missed = [record for record in records if not record.is_correct]
        if not missed:
            lines.append("No missed questions in this section.")
        else:
            for index, record in enumerate(missed, start=1):
                passage = bank.passages.get(record.passage_id)
                lines.append(f"**{index}. {record.stem_en} — {item_level_label(record)}**")
                lines.append(f"- Your answer: {record.selected_key or 'No answer'}")
                lines.append(f"- Correct answer: {record.correct_key}. {record.choices_snapshot[record.correct_key]}")
                lines.append(f"- Explanation: {record.rationale_en}")
                lines.append(f"- Russian evidence: `{record.evidence_ru}`")
                if skill == "listening" and state.transcript_review_enabled and passage:
                    lines.append(f"- Transcript: {passage.passage_ru}")
    return "\n\n".join(lines)


def build_full_report(state: SessionState, bank: ItemBank) -> str:
    lines = [
        "# Session Report",
        "This is an independent practice report, not an official DLPT score or government assessment.",
        f"Session code: `{state.session_id}`",
        (
            f"Content policy: Fresh AI preferred; {len(state.generated_passage_ids)} new passage(s) accepted and stored, "
            f"{state.generation_failures} generation/validation failure(s), and {state.bank_fallback_count} bank fallback(s)."
            if state.content_source == "fresh_ai_preferred"
            else "Content policy: Validated bank only."
        ),
    ]
    for skill in state.selected_skills:
        lines.append(build_skill_report(state, skill, bank, include_review=True))
    return "\n\n---\n\n".join(lines)


def build_exports(state: SessionState, export_dir: str | Path) -> tuple[str, str]:
    return str(export_session_json(state, export_dir)), str(export_responses_csv(state, export_dir))
