from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from core.adaptive import initialize_ability, update_ability
from core.bank_persistence import GeneratedBankPersistence
from core.config import Settings
from core.item_bank import ItemBank
from core.models import ResponseRecord
from core.prompts import passage_authoring_prompt
from core.session import create_session, record_answer_change, select_next_bundle, submit_current_bundle
from core.validation import answer_length_leakage_summary, choice_length_leakage_flags


def _response(question_id: str, passage_id: str, correct: bool) -> ResponseRecord:
    return ResponseRecord(
        session_id="testlet",
        passage_id=passage_id,
        question_id=question_id,
        skill="reading",
        mode="diagnostic",
        language="ru",
        target_ilr="2",
        item_difficulty=0.5,
        item_discrimination=1.0,
        question_type="inference",
        topic="Public policy",
        genre="report",
        stem_en="What conclusion is supported?",
        choices_snapshot={"A": "One", "B": "Two", "C": "Three", "D": "Four"},
        rationale_en="The passage evidence supports this answer.",
        evidence_ru="подтверждающий текст",
        selected_key="A",
        correct_key="A" if correct else "B",
        is_correct=correct,
        response_time_seconds=10.0,
    )


def _state(skill: str = "reading", mode: str = "training"):
    return create_session(
        mode=mode,
        selected_skills=[skill],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=12 if mode == "simulation" else 8,
        minimum_questions_per_skill=8,
        timer_mode="strict" if mode == "simulation" else "off",
        time_limit_seconds_per_skill=300 if mode == "simulation" else None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=mode == "training",
        slow_audio_allowed=mode == "training",
        voice_label="Starter-bank Russian voice",
        speech_rate_label="Normal",
        shortened_simulation=mode == "simulation",
    )


def test_passage_testlet_discount_preserves_more_uncertainty():
    same_passage = [_response(f"q{i}", "shared", i % 2 == 0) for i in range(4)]
    separate_passages = [_response(f"q{i}", f"p{i}", i % 2 == 0) for i in range(4)]
    same = update_ability(initialize_ability("reading", "2", broad=True), same_passage)
    separate = update_ability(initialize_ability("reading", "2", broad=True), separate_passages)
    assert same.standard_error > separate.standard_error


def test_response_times_use_each_final_selection_timestamp(bank):
    state = _state()
    bundle = select_next_bundle(state, bank)
    state.current_started_at_epoch = 100.0
    for index, question in enumerate(bundle.questions):
        record_answer_change(state, question.id, question.correct_key, now=105.0 + index * 3.0)
    records = submit_current_bundle(
        state,
        bundle.passage,
        bundle.questions,
        dict(state.current_answers),
        "timing",
        now=130.0,
    )
    assert [record.response_time_seconds for record in records] == [5.0 + index * 3.0 for index in range(len(records))]


def test_server_audio_preparation_does_not_consume_strict_play(monkeypatch, bank):
    import ui.callbacks as callbacks

    state = _state("listening", "simulation")
    bundle = select_next_bundle(state, bank)
    bundle_data = callbacks._bundle_to_dict(bundle)
    monkeypatch.setattr(callbacks.STORAGE, "save_checkpoint", lambda *_: None)
    prepared = callbacks.play_audio_callback(state, bundle_data, progress=None)
    assert prepared[0].current_listening_plays == 0
    confirmed = callbacks.confirm_audio_playback_callback(state, bundle_data)
    assert confirmed[0].current_listening_plays == 1


def test_expired_timer_auto_submits_answers_selected_before_deadline(monkeypatch, bank):
    import ui.callbacks as callbacks

    state = _state("reading", "simulation")
    bundle = select_next_bundle(state, bank)
    state.current_started_at_epoch = 90.0
    state.skill_deadline_epoch = 110.0
    for index, question in enumerate(bundle.questions):
        record_answer_change(state, question.id, question.correct_key, now=100.0 + index)
    monkeypatch.setattr(callbacks.time, "time", lambda: 111.0)
    monkeypatch.setattr(callbacks.STORAGE, "save_checkpoint", lambda *_: None)
    monkeypatch.setattr(callbacks, "build_full_report", lambda *_: "report")
    monkeypatch.setattr(callbacks, "build_exports", lambda *_: ("session.json", "responses.csv"))
    result = callbacks.expire_section_callback(state, callbacks._bundle_to_dict(bundle), "expiry")
    assert result[0].status == "completed"
    assert len(result[0].responses) == len(bundle.questions)


def test_answer_length_diagnostic_finds_material_keying_cue(bank):
    original = bank.questions["r001_q1"]
    leaky = original.model_copy(update={
        "choices": {
            "A": "The city office",
            "B": "The school",
            "C": "The train station that serves every northern regional community",
            "D": "The clinic",
        },
        "correct_key": "C",
    })
    assert "correct_choice_materially_longer_than_every_distractor" in choice_length_leakage_flags(leaky)
    summary = answer_length_leakage_summary([leaky])
    assert summary["longest_strategy_expected_rate"] == 1.0


def test_starter_banks_have_no_uniquely_longest_correct_answer(bank):
    for language in ("ru", "zh-CN"):
        for skill in ("reading", "listening"):
            questions = [
                question
                for passage in bank.active_passages(skill, language)
                for question in bank.get_questions(passage.id)
            ]
            summary = answer_length_leakage_summary(questions)
            assert summary["correct_unique_longest"] == 0
            assert summary["materially_flagged"] == 0


def test_high_level_mandarin_reading_prompts_cover_both_character_systems():
    prompts = [
        passage_authoring_prompt(
            skill="reading",
            mode="training",
            level="3",
            topics=[],
            competencies=[],
            novelty_context=[],
            generation_nonce=f"nonce-{index}",
            language="zh-CN",
        )
        for index in range(20)
    ]
    assert any("Traditional Chinese" in prompt for prompt in prompts)
    assert any("Simplified Chinese" in prompt for prompt in prompts)


def test_mandarin_starter_rationales_are_specific(project_root):
    rationales = []
    for line in (project_root / "data/mandarin_starter_items.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["kind"] == "question":
            rationales.append(record["data"]["rationale_en"])
    assert len(rationales) == 72
    assert len(set(rationales)) == 72
    assert all("By contrast" in rationale for rationale in rationales)


def test_generated_overlay_cannot_overwrite_or_extend_starter_ids(project_root, tmp_path):
    starter = project_root / "data/starter_items.jsonl"
    original = ItemBank(starter).load().passages["r001"]
    forged_passage = original.model_copy(update={"passage_ru": "Подмененный текст"})
    forged_question = ItemBank(starter).load().questions["r001_q1"].model_copy(
        update={"id": "forged_q", "passage_id": "r001"}
    )
    overlay = tmp_path / "generated.jsonl"
    overlay.write_text(
        json.dumps({"kind": "passage", "data": forged_passage.model_dump(mode="json")}, ensure_ascii=False)
        + "\n"
        + json.dumps({"kind": "question", "data": forged_question.model_dump(mode="json")}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    bank = ItemBank([starter, overlay], writable_path=overlay).load()
    assert bank.passages["r001"].passage_ru == original.passage_ru
    assert "forged_q" not in bank.questions
    assert len(bank.load_warnings) == 2


def test_backup_import_rejects_archive_bomb_ratio(project_root, tmp_path):
    source = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("generated_items.jsonl", b"0" * (2 * 1024 * 1024))
    settings = Settings(
        generated_item_bank_path=tmp_path / "generated.jsonl",
        generated_bank_manifest_path=tmp_path / "generated.meta.json",
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
        session_dir=tmp_path / "sessions",
        history_dir=tmp_path / "history",
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    with pytest.raises(ValueError, match="compression ratio"):
        persistence.import_backup(source)


def test_production_launch_hides_framework_tracebacks():
    import app

    assert app.launch_kwargs()["show_error"] is False
