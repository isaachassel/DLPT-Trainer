from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .item_bank import ItemBank
from .languages import language_profile
from .models import ResponseRecord, SessionState
from .scoring import accuracy, estimate_label, grouped_accuracy, item_level_label, response_time_summary, strengths_and_weaknesses
from .storage import export_responses_csv, export_session_json
from . import assessment
from .adaptive import nearest_ilr


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
            "Item levels were hidden during active Diagnostic and DLPT-style Simulation sections. "
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


def _adaptive_route_review(state: SessionState, skill: str) -> list[str]:
    estimate = state.ability_for(skill)
    lines = [
        "### Adaptive routing review",
        (
            f"Eligible range: **ILR {state.minimum_ilr} through ILR {state.maximum_ilr}**. "
            "The continuous Bayesian estimate is used for scoring; the delivery band moves conservatively "
            "by no more than one adjacent ILR half-step after each completed passage."
        ),
    ]
    if not estimate.routing_history:
        return lines + [f"No completed routing decisions. Initial delivery band: **ILR {estimate.routing_ilr}**."]
    route = [estimate.routing_history[0]["from_ilr"]]
    route.extend(event["to_ilr"] for event in estimate.routing_history)
    lines.append("**Passage routing path:** " + " → ".join(f"ILR {level}" for level in route))
    lines.append(f"**Next/final routing band:** ILR {estimate.routing_ilr}")
    for index, event in enumerate(estimate.routing_history, start=1):
        movement = (
            "held"
            if event["from_ilr"] == event["to_ilr"]
            else f"moved {event['from_ilr']} → {event['to_ilr']}"
        )
        lines.append(
            f"- Passage {index}: {event['bundle_correct']}/{event['bundle_total']} correct; "
            f"{movement}; {event['reason']}."
        )
    return lines

def _recommendation(records: list[ResponseRecord], estimate_level: str | None, weaknesses: list[str]) -> str:
    if len(records) < 8:
        return (
            "Complete at least eight balanced questions in this skill before treating any topic, genre, or "
            "competency as a personal strength or weakness. Continue near the current routing band."
        )
    level = estimate_level or "the current working band"
    weak_text = ", ".join(weaknesses) if weaknesses else "mixed comprehension skills"
    genres = grouped_accuracy(records, "genre")
    lowest_genre = min(genres.items(), key=lambda x: x[1][2])[0] if genres else "mixed real-world texts"
    return (
        f"Next session: complete 12–16 questions near ILR {level}; emphasize {weak_text}; "
        f"include at least two {lowest_genre} passages; then retest one adjacent higher band only after accuracy stabilizes."
    )


def build_skill_report(state: SessionState, skill: str, bank: ItemBank, include_review: bool = True) -> str:
    if state.mode == "assessment":
        return _assessment_report(state, skill, bank, include_review)
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
    if state.minimum_ilr != "0" or state.maximum_ilr != "3":
        lines.append(
            "**Range-limited interpretation:** this estimate was produced only from the configured ILR band range "
            "and should not be interpreted as a full-spectrum diagnostic outside that range."
        )
    lines.extend(_adaptive_route_review(state, skill))
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
                lines.append(f"- {language_profile(record.language).short_label} evidence: `{record.evidence_ru}`")
                if skill == "listening" and state.transcript_review_enabled and passage:
                    lines.append(f"- Transcript: {passage.passage_ru}")
    return "\n\n".join(lines)


def build_full_report(state: SessionState, bank: ItemBank) -> str:
    if state.mode == "assessment" and state.status == "active":
        return "Assessment in progress. Results and explanations are withheld until all selected skill sections end."
    lines = [
        "# Session Report",
        f"Language: {language_profile(state.language).label}",
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
    if state.mode == "assessment":
        return "\n\n".join(lines)
    return "\n\n---\n\n".join(lines)


def _assessment_report(state: SessionState, skill: str, bank: ItemBank, include_review: bool) -> str:
    if state.status == "active":
        return "Assessment in progress. Results and explanations are withheld until all selected skill sections end."
    estimate = state.ability_for(skill)
    records = state.responses_for(skill)
    count = assessment.passage_count(state, skill)
    reason = state.assessment_end_reasons.get(skill, "abandoned")
    lines = [f"## {skill.title()} Adaptive Assessment",
             f"**Why it ended:** {assessment.END_REASONS[reason]}",
             f"Evidence: **{count} passages / {len(records)} questions**, {sum(r.is_correct for r in records)} correct.",
             f"Configured limits: {state.assessment_min_passages}–{state.assessment_max_passages} passages; posterior SD target {state.assessment_target_sd:.2f}."]
    if count < state.assessment_min_passages:
        lines.append("**Insufficient evidence: no estimated practice ILR level is reported.** The minimum passage count was not reached.")
    else:
        probabilities = assessment.band_probabilities(estimate)
        mass = probabilities[estimate.practice_ilr]
        lines.append(f"**Estimated practice ILR level: {estimate.practice_ilr} (provisional).** "
                     f"Model probability in that band: {mass:.0%}.")
        if not assessment.precision_met(state, skill) or mass < 0.60 or reason == "abandoned":
            lines.append("**Inconclusive classification:** uncertainty remains too broad or crosses a band boundary. "
                         "Use the interval rather than treating the point estimate as a settled level.")
        else:
            lines.append("The configured evidence target was met; the estimate remains unvalidated practice guidance.")
    if records:
        lines.append(f"**90% posterior credible interval:** {estimate.ci_low:.2f} to {estimate.ci_high:.2f} on the internal scale "
                     f"(approximately practice ILR {nearest_ilr(estimate.ci_low)}–{nearest_ilr(estimate.ci_high)}); "
                     f"**posterior SD: {estimate.standard_error:.2f}**.")
        if estimate.ci_low < -2.5 or estimate.ci_high > 2.0:
            lines.append("The interval extends beyond the bank's ILR 0–3 anchors. Endpoint labels pool the tails; "
                         "this bank cannot resolve ability beyond those limits.")
    if state.minimum_ilr != "0" or state.maximum_ilr != "3":
        lines.append(f"Range-limited assessment: only ILR {state.minimum_ilr}–{state.maximum_ilr} content was eligible.")
    lines.append("Bayesian passage-testlet model: a 25% guessing allowance for four-choice questions and a shared "
                 "passage difficulty offset account for related responses. ILR labels and model parameters are provisional. "
                 "The interval is conditional on these assumptions and excludes unknown systematic labeling error. "
                 "This does not reproduce the official ODA/DLPT algorithm or provide a validated official score.")
    if include_review and records:
        lines.append("### Answer and explanation review")
        last_passage = None
        for index, record in enumerate(records, 1):
            if skill == "listening" and record.passage_id != last_passage:
                passage = bank.passages.get(record.passage_id)
                if passage and state.transcript_review_enabled:
                    lines.append(f"**Listening transcript:** {passage.passage_ru}")
            last_passage = record.passage_id
            lines.extend([f"**{index}. {record.stem_en}** — {'Correct' if record.is_correct else 'Incorrect'}",
                          f"Your answer: {record.selected_key}. Correct answer: {record.correct_key}. {record.choices_snapshot[record.correct_key]}",
                          f"Explanation: {record.rationale_en}", f"Evidence: {record.evidence_ru}"])
    return "\n\n".join(lines)


def build_exports(state: SessionState, export_dir: str | Path) -> tuple[str, str]:
    return str(export_session_json(state, export_dir)), str(export_responses_csv(state, export_dir))
