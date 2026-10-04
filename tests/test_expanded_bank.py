"""Real packaged content checks; no network or provider calls."""
from collections import Counter
import pytest
from core import assessment
from core.constants import ILR_LEVELS
from core.preset_bank import PresetBank, ROOT, read_package
from core.reporting import build_full_report
from core.session import select_next_bundle, advance_skill_or_finish
from core.validation import choice_length_leakage_flags, near_duplicate, validate_question
from tests.test_assessment import state_for, answer


def test_both_skills_cover_every_band_with_distinct_validated_content():
    bank = PresetBank().load()
    assert not bank.load_warnings
    for skill in ("reading", "listening"):
        passages = bank.active_passages(skill, "ru")
        counts = Counter(p.target_ilr for p in passages)
        assert set(counts) == set(ILR_LEVELS)
        assert all(counts[level] >= 2 for level in ILR_LEVELS)
        assert len({p.content_hash for p in passages}) == len(passages)
        for p in passages:
            for q in bank.get_questions(p.id):
                assert validate_question(q, p).status == "accepted"
                assert not choice_length_leakage_flags(q)
            if p.target_ilr == "3":
                assert any(q.question_type in {"inference", "relationship of ideas", "meaning from context"}
                           for q in bank.get_questions(p.id))
    new = read_package(ROOT / "data/pilots/russian_range_expansion.json").items
    assert all(not near_duplicate(a.passage.passage_ru, b.passage.passage_ru)
               for n, a in enumerate(new) for b in new[n + 1:])


@pytest.mark.parametrize("skill", ["reading", "listening"])
@pytest.mark.parametrize("strong", [True, False])
def test_real_expansion_routes_up_and_down_without_repeating(skill, strong):
    bank = PresetBank().load()
    state = state_for([skill], assessment_min_passages=12, assessment_max_passages=12)
    delivered = []
    while state.status == "active":
        bundle = select_next_bundle(state, bank)
        delivered.append(bundle.passage.target_ilr)
        answer(state, bundle, strong)
        advance_skill_or_finish(state)
    assert len(set(state.completed_passage_ids)) == len(state.completed_passage_ids) == 12
    indexes = [ILR_LEVELS.index(x) for x in delivered]
    assert max(indexes) > indexes[0] if strong else min(indexes) < indexes[0]
    assert ("3" if strong else "0") in delivered
    assert state.assessment_end_reasons[skill] == "maximum"
    assert "Answer and explanation review" in build_full_report(state, bank)


def test_single_band_filter_stays_explicitly_inconclusive():
    bank = PresetBank().load()
    state = state_for(["reading"], minimum_ilr="3", maximum_ilr="3",
                      assessment_min_passages=2, assessment_max_passages=2)
    while state.status == "active":
        bundle = select_next_bundle(state, bank)
        assert bundle.passage.target_ilr == "3"
        answer(state, bundle)
        advance_skill_or_finish(state)
    assert not assessment.precision_met(state, "reading")
    report = build_full_report(state, bank)
    assert "Limited difficulty coverage" in report and "Inconclusive classification" in report
