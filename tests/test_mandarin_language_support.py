from __future__ import annotations

from core.config import Settings
from core.item_bank import ItemBank
from core.generation import (
    CandidatePassageDraft,
    LiveGenerationService,
    PassageAudit,
    _audit_issues,
    _level3_listening_duration_issue,
    validate_candidate_passage,
)
from core.languages import language_profile, voice_choices, voice_for_label
from core.prompts import passage_authoring_prompt, question_authoring_prompt
from core.session import create_session, select_next_bundle
from core.validation import content_hash, normalize_text, target_language_ratio, target_unit_count


def multilingual_bank(project_root) -> ItemBank:
    return ItemBank([
        project_root / "data" / "starter_items.jsonl",
        project_root / "data" / "mandarin_starter_items.jsonl",
    ]).load()


def session(language: str, skill: str):
    return create_session(
        language=language,
        mode="training",
        selected_skills=[skill],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_of_passage",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label=language_profile(language).starter_voice_label,
        speech_rate_label="Normal",
    )


def test_mandarin_bank_has_full_skill_and_ilr_coverage(project_root):
    bank = multilingual_bank(project_root)
    health = bank.health_summary("zh-CN")
    assert health["reading"]["ready_passages"] == 12
    assert health["reading"]["ready_questions"] == 36
    assert health["listening"]["ready_passages"] == 12
    assert health["listening"]["ready_questions"] == 36
    assert health["listening"]["ready_audio_assets"] == 12
    assert all(health[skill]["ready_ilr_question_counts"][level] > 0 for skill in ("reading", "listening") for level in ("0", "0+", "1", "1+", "2", "2+", "3"))


def test_language_selection_never_crosses_banks(project_root):
    bank = multilingual_bank(project_root)
    chinese = select_next_bundle(session("zh-CN", "reading"), bank)
    russian = select_next_bundle(session("ru", "reading"), bank)
    assert chinese.passage.language == "zh-CN"
    assert russian.passage.language == "ru"
    assert chinese.passage.id.startswith("zh_r")
    assert not russian.passage.id.startswith("zh_")


def test_mandarin_listening_selection_has_playable_audio(project_root):
    bank = multilingual_bank(project_root)
    bundle = select_next_bundle(session("zh-CN", "listening"), bank)
    asset = bank.get_audio(bundle.passage.audio_asset_id)
    assert bundle.passage.language == "zh-CN"
    assert asset is not None and asset.validated
    assert asset.voice == "zh-CN-XiaoxiaoNeural"
    assert (project_root / asset.path).stat().st_size > 512


def test_mandarin_normalization_and_hashing_are_not_empty():
    text = "普通话阅读练习"
    assert normalize_text(text)
    assert target_unit_count(text, "zh-CN") == 7
    assert target_language_ratio(text, "zh-CN") == 1.0
    assert content_hash(text) != content_hash("俄罗斯语阅读练习")


def test_mandarin_generation_prompts_are_language_specific():
    passage_prompt = passage_authoring_prompt(
        skill="reading", mode="training", level="2", topics=[], competencies=[],
        novelty_context=[], generation_nonce="test", language="zh-CN",
    )
    question_prompt = question_authoring_prompt(
        skill="reading", mode="training", level="2", desired_count=3,
        competencies=[], passage_json='{"passage_ru":"中文"}', language="zh-CN",
    )
    assert "Mandarin Chinese" in passage_prompt
    assert "Chinese characters" in passage_prompt
    assert "Mandarin Chinese" in question_prompt


def test_language_specific_voice_routing():
    choices = voice_choices("zh-CN")
    assert "Mandarin Female — Xiaoxiao" in choices
    assert voice_for_label("zh-CN", "Mandarin Male — Yunxi") == "zh-CN-YunxiNeural"
    assert Settings().tts_voice_for("zh-CN") == "zh-CN-XiaoxiaoNeural"


def test_mock_live_generation_materializes_mandarin(project_root, tmp_path):
    overlay = tmp_path / "generated.jsonl"
    overlay.write_text("", encoding="utf-8")
    bank = ItemBank([
        project_root / "data" / "starter_items.jsonl",
        project_root / "data" / "mandarin_starter_items.jsonl",
        overlay,
    ], writable_path=overlay).load()
    settings = Settings(
        generation_provider="mock",
        verification_provider="mock",
        generation_audit_mode="always",
        generated_item_bank_path=overlay,
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
    )
    result = LiveGenerationService(settings, bank, project_root).generate_and_store(
        language="zh-CN", skill="reading", level="2", mode="training",
        topics=[], competencies=[], maximum_questions=3,
    )
    assert result.passage.language == "zh-CN"
    assert target_language_ratio(result.passage.passage_ru, "zh-CN") > 0.9
    assert all(question.evidence_ru in result.passage.passage_ru for question in result.questions)


def test_mandarin_audit_uses_mandarin_specific_naturalness_flag():
    audit = PassageAudit(
        acceptable=True,
        estimated_ilr="3",
        confidence=0.9,
        natural_target_language=False,
        coherent=True,
        orientation_safe=True,
        level_match=True,
        protected_content_risk=False,
        translation_artifacts=[],
        contradiction_flags=[],
        repetition_flags=[],
        repair_notes=[],
    )
    issues = _audit_issues(audit, "3", language="zh-CN")
    assert "independent_audit_detected_unnatural_mandarin" in issues
    assert not any("russian" in issue for issue in issues)


def test_mandarin_level3_sentence_limits_use_characters_not_spaces():
    natural_sentences = "。".join(["这段评论分析政策变化对地方企业和普通家庭可能产生的长期影响" for _ in range(9)]) + "。"
    candidate = CandidatePassageDraft(
        passage_ru=natural_sentences,
        orientation_en="A policy commentary",
        topic="public policy",
        subtopic="local effects",
        genre="commentary",
        register_name="formal",
        text_mode="spoken",
        target_ilr="3",
        provisional_difficulty=2.4,
        discourse_features=["connected argument"],
        vocabulary_features=["policy vocabulary"],
    )
    issues = validate_candidate_passage(candidate, skill="listening", requested_level="3", language="zh-CN")
    assert "listening_sentence_too_long_for_natural_tts" not in issues
    assert "unreasonably_long_sentence_detected" not in issues


def test_level3_listening_duration_target_is_two_to_two_and_a_half_minutes():
    assert _level3_listening_duration_issue(119.9) == "level3_listening_audio_below_2_minute_target"
    assert _level3_listening_duration_issue(120.0) is None
    assert _level3_listening_duration_issue(150.0) is None
    assert _level3_listening_duration_issue(150.1) == "level3_listening_audio_exceeds_2_5_minute_limit"
