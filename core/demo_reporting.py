"""Plain-language demo results; presentation only, never changes ability scoring."""
from html import escape

from .adaptive import nearest_ilr
from .constants import ILR_LEVELS, ILR_THETA
from .languages import language_profile
from .models import SessionState
from .scoring import grouped_accuracy


def demo_end_reason(state: SessionState, skill: str) -> str:
    reason = state.assessment_end_reasons.get(skill)
    if reason == "content_exhausted":
        return "The bank ran out of unused approved passages for this test."
    if reason == "time_limit" or state.status == "expired":
        return "The time limit was reached. Only submitted answers count."
    if state.status == "error":
        return "A problem interrupted the test. Your submitted answers were saved."
    if state.completed_count(skill) >= state.max_questions_per_skill:
        return f"All {state.max_questions_per_skill} questions were completed."
    return "The test ended before all questions were completed."


def build_demo_report(state: SessionState) -> str:
    """Render escaped HTML with no results or answer leakage during an active test.

    A rough location is useful even when the strict stable-band rule fails. The
    minimum below is a display safeguard, not a validated classification rule.
    Confidence and the underlying stored estimate are never upgraded here.
    """
    if state.status == "active":
        return ""
    sections = []
    for skill in state.selected_skills:
        records = state.responses_for(skill)
        count = len(records)
        passages = len({r.passage_id for r in records})
        correct = sum(r.is_correct for r in records)
        estimate = state.ability_for(skill)
        enough = (count >= 8 and passages >= 3 and estimate.items_answered == count
                  and bool(estimate.posterior_weights))
        level = nearest_ilr(estimate.theta) if enough else None
        title = f"{language_profile(state.language).label} · {skill.title()} results"
        lines = ['<section class="demo-result">', f'<h2>{escape(title)}</h2>']
        if level is not None:
            lines += ['<p class="demo-result-label">Estimated practice level</p>',
                      f'<p class="demo-result-level">Around ILR {level}</p>',
                      f'<p>Your answers suggest starting {skill} practice around this level.</p>']
        else:
            lines += ['<h3>Not enough answers to estimate a level yet</h3>',
                      '<p>Try a complete test. We need answers from several different passages.</p>']
        lines.append(f'<p><strong>{correct} of {count} correct</strong> · {passages} passages</p>')
        if enough:
            confidence = "Limited" if estimate.stable else "Low"
            lines.append(f'<div class="demo-result-confidence"><strong>Confidence: {confidence}</strong>'
                         f'<p>This short test sampled only {passages} passages. '
                         'Use the result as a starting point, not a confirmed level.</p>')
            low, high = nearest_ilr(estimate.ci_low), nearest_ilr(estimate.ci_high)
            spread = f'ILR {low} to {high}' if low != high else f'around ILR {low}'
            lines.append(f'<p>The current model leaves room for a result {"from " if low != high else ""}'
                         f'{spread}. More varied passages would help narrow it down.</p></div>')
            if estimate.ci_low < ILR_THETA["0"] or estimate.ci_high > ILR_THETA["3"]:
                lines.append('<p>This demo covers ILR 0–3; it cannot distinguish levels beyond those limits.</p>')
        lines.append(f'<p><strong>Why the test ended:</strong> {demo_end_reason(state, skill)}</p>')
        if records:
            grouped = grouped_accuracy(records, "target_ilr")
            lines.append('<h3>How you did</h3><table><thead><tr><th>Passage level</th>'
                         '<th>Correct answers</th></tr></thead><tbody>')
            for band in sorted(grouped, key=ILR_LEVELS.index):
                right, total, _ = grouped[band]
                lines.append(f'<tr><td>ILR {escape(band)}</td><td>{right} of {total}</td></tr>')
            lines.append('</tbody></table><p>Passage levels are estimated. '
                         'Getting harder questions right carries more weight than the overall percentage.</p>')
            if len(grouped) == 1:
                lines.append('<p><strong>Limited coverage:</strong> You answered passages at just one level. '
                             'Performance at other levels has not been tested.</p>')
        lines.append('<p class="demo-result-note">This is an unvalidated practice estimate, not an official '
                     'DLPT score or a reliable prediction of one. For a useful personal estimate, '
                     'take the test without translation tools or outside help.</p>')
        lines.append('<details><summary>How this estimate works</summary>'
                     '<p>The estimate combines answer accuracy and question difficulty, allows for guessing, '
                     'and gives less weight to questions sharing a passage. '
                     'The displayed range rounds the model’s middle 80% range to nearby ILR labels. '
                     'It assumes our difficulty labels are reasonable; it does not measure how accurate '
                     'those labels are. The bank has not been calibrated against real test-taker results.</p></details>')
        missed = [r for r in records if not r.is_correct]
        if missed:
            lines.append(f'<details><summary>Review missed questions ({len(missed)})</summary>')
            for index, record in enumerate(missed, 1):
                selected = record.selected_key
                answer = (f'{selected}. {record.choices_snapshot.get(selected, "")}'
                          if selected else 'No answer')
                right = f'{record.correct_key}. {record.choices_snapshot.get(record.correct_key, "")}'
                lines += [f'<h4>{index}. {escape(record.stem_en)}</h4>',
                          f'<p><strong>Your answer:</strong> {escape(answer)}</p>',
                          f'<p><strong>Correct answer:</strong> {escape(right)}</p>',
                          f'<p>{escape(record.rationale_en)}</p>',
                          f'<p><strong>Passage evidence:</strong> {escape(record.evidence_ru)}</p>']
            lines.append('</details>')
        elif records:
            lines.append('<p>No missed questions to review.</p>')
        lines.append('</section>')
        sections.append(''.join(lines))
    return ''.join(sections)
