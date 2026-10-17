"""Demo display safeguards without private learner checkpoints as fixtures."""
import pytest

from core.adaptive import initialize_ability
from core.demo_reporting import build_demo_report, demo_end_reason
from core.models import ResponseRecord, SessionState


@pytest.fixture
def completed():
    records = [ResponseRecord(
        session_id='synthetic', passage_id=f'p{i // 3}', question_id=f'q{i}',
        skill='reading', mode='simulation', target_ilr='2' if i < 6 else '2+',
        item_difficulty=.5 if i < 6 else 1.25, question_type='detail', topic='daily life',
        genre='article', stem_en=f'Question {i}', choices_snapshot={'A': 'Right', 'B': 'Wrong'},
        rationale_en='Explanation', evidence_ru='Evidence', selected_key='A' if i < 8 else 'B',
        correct_key='A', is_correct=i < 8, response_time_seconds=20,
    ) for i in range(12)]
    estimate = initialize_ability('reading').model_copy(update={
        'theta': .45, 'ci_low': -.7, 'ci_high': 1.55, 'standard_error': .90,
        'items_answered': 12, 'correct': 8, 'practice_ilr': None, 'stable': False, 'confidence': 'low',
    })
    return SessionState(mode='simulation', selected_skills=['reading'], session_started_at_epoch=0,
                        reading_ability=estimate, listening_ability=initialize_ability('listening'),
                        status='completed', max_questions_per_skill=12, responses=records, demo_mode=True)


@pytest.mark.parametrize('theta,level', [(-1.75, '0+'), (-.03, '1+'), (.45, '2'), (.874, '2'), (.876, '2+')])
def test_rough_location_not_hidden_by_strict_stability_rule(completed, theta, level):
    completed.reading_ability.theta = theta
    before = completed.model_dump()
    report = build_demo_report(completed)
    assert f'Around ILR {level}' in report
    assert 'Confidence: Low' in report
    assert '8 of 12 correct' in report and '4 passages' in report
    assert 'ILR 1 to 2+' in report
    assert 'not an official DLPT score' in report
    assert 'Insufficient evidence for a stable' not in report
    assert completed.model_dump() == before  # reporting must not change scoring


@pytest.mark.parametrize('questions,passages', [(0, 0), (6, 3), (12, 1), (12, 2)])
def test_sparse_results_do_not_report_prior_as_level(completed, questions, passages):
    completed.responses = completed.responses[:questions]
    for i, record in enumerate(completed.responses):
        record.passage_id = f'p{i % passages}'
    completed.reading_ability.items_answered = questions
    report = build_demo_report(completed)
    assert 'Not enough answers' in report
    assert 'Around ILR' not in report


def test_active_results_and_answers_are_withheld(completed):
    completed.status = 'active'
    assert build_demo_report(completed) == ''


def test_review_is_collapsed_and_escaped(completed):
    completed.responses[-1].stem_en = '<script>alert(1)</script>'
    report = build_demo_report(completed)
    assert '<details><summary>Review missed questions (4)</summary>' in report
    assert '<script>' not in report
    assert '&lt;script&gt;' in report
    assert 'B. Wrong' in report and 'A. Right' in report


@pytest.mark.parametrize('reason,text', [('content_exhausted', 'ran out'), ('time_limit', 'time limit')])
def test_stopping_reason_is_explicit(completed, reason, text):
    completed.assessment_end_reasons['reading'] = reason
    assert text in build_demo_report(completed)


def test_early_stop_and_completed_count(completed):
    assert 'All 12 questions' in demo_end_reason(completed, 'reading')
    completed.responses = completed.responses[:9]
    assert 'before all questions' in demo_end_reason(completed, 'reading')


def test_stable_model_does_not_claim_validated_confidence(completed):
    completed.reading_ability.stable = True
    completed.reading_ability.confidence = 'high'
    report = build_demo_report(completed)
    assert 'Confidence: Limited' in report
    assert 'unvalidated practice estimate' in report


def test_single_band_and_bank_limits_explained(completed):
    for r in completed.responses:
        r.target_ilr = '3'
    completed.reading_ability.theta = 2.2
    completed.reading_ability.ci_high = 3
    report = build_demo_report(completed)
    assert 'Around ILR 3' in report
    assert 'just one level' in report
    assert 'cannot distinguish levels beyond' in report
