from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.config import Settings, get_settings
from core.generation import (
    AUTHORING_SYSTEM,
    VERIFIER_SYSTEM,
    AuthoringProvider,
    BlindVerification,
    BlindVerificationBatch,
    CandidatePassageDraft,
    CandidateQuestionSet,
    HostedProvider,
    LiveGenerationService,
    MockProvider,
    PassageAudit,
    validate_with_blind_verifier,
    validate_with_blind_verifier_batch,
)
from core.item_bank import ItemBank
from core.prompts import PROMPT_VERSION


class RecordingMock(MockProvider):
    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, str, str]] = []

    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        self.calls.append((system, prompt, schema.__name__))
        return super().generate_json(
            system, prompt, schema, max_tokens=max_tokens, temperature=temperature
        )


class BlindRecordingProvider(AuthoringProvider):
    def __init__(self, correct_text: str, evidence_quote: str):
        super().__init__()
        self.correct_text = correct_text
        self.evidence_quote = evidence_quote
        self.prompt = ""

    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        self.usage.add(10, 10)
        self.prompt = prompt
        marker = prompt.split("<CHOICES_ZERO_BASED>", 1)[1].split("</CHOICES_ZERO_BASED>", 1)[0]
        choices = json.loads(marker.strip())
        selected = choices.index(self.correct_text)
        return BlindVerification(
            selected_index=selected,
            second_best_index=-1,
            confidence=0.95,
            multiple_plausible=False,
            requires_outside_knowledge=False,
            evidence_sufficient=True,
            reasoning_match=True,
            answer_leakage=False,
            evidence_quote_ru=self.evidence_quote,
            explanation="The source directly supports the selected option.",
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        generation_provider="mock",
        generated_item_bank_path=tmp_path / "generated.jsonl",
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
        session_dir=tmp_path / "sessions",
        history_dir=tmp_path / "history",
    )


def test_prompt_source_has_no_fixed_answer_letter_sequence(project_root):
    text = (project_root / "core/prompts.py").read_text(encoding="utf-8").casefold()
    forbidden = ["q1=a", "q2=b", "q3=c", "q4=d", '"correct_key": "a"', "correct answer letter"]
    assert all(pattern not in text for pattern in forbidden)
    assert "zero-based index" in text
    assert PROMPT_VERSION == "genai-pipeline-v11"


def test_blind_verifier_never_receives_proposed_key(project_root):
    bank = ItemBank([project_root / "data/starter_items.jsonl"]).load()
    passage = bank.get_passage("r001")
    question = bank.get_questions("r001")[0]
    provider = BlindRecordingProvider(question.choices[question.correct_key], question.evidence_ru)

    report = validate_with_blind_verifier(provider, passage, question)

    assert report.status == "accepted"
    assert "proposed_correct" not in provider.prompt
    assert "correct_key" not in provider.prompt
    assert f"Proposed answer: {question.correct_key}" not in provider.prompt


def test_generation_pipeline_uses_separate_stages_and_verifier(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    author = RecordingMock()
    verifier = RecordingMock()
    service = LiveGenerationService(
        _settings(tmp_path), bank, project_root, provider=author, verifier_provider=verifier
    )

    result = service.generate_and_store(
        skill="reading", level="2", mode="training", topics=["education"],
        competencies=["main idea", "prominent detail"], maximum_questions=2,
    )

    author_schemas = [schema for _, _, schema in author.calls]
    verifier_schemas = [schema for _, _, schema in verifier.calls]
    assert author_schemas[:2] == [CandidatePassageDraft.__name__, CandidateQuestionSet.__name__]
    assert PassageAudit.__name__ in verifier_schemas
    assert verifier_schemas.count(BlindVerificationBatch.__name__) == 1
    assert all(system == AUTHORING_SYSTEM for system, _, _ in author.calls)
    assert all(system == VERIFIER_SYSTEM for system, _, _ in verifier.calls)
    assert result.request_count >= 4
    assert result.passage.generation.request_count == result.request_count
    assert result.passage.generation.pipeline_version == PROMPT_VERSION


def test_strict_schema_is_sent_before_json_object_fallback(monkeypatch):
    settings = Settings(
        generation_provider="huggingface",
        hf_token="not-a-real-key",
        structured_output_mode="auto",
        provider_max_retries=0,
    )
    provider = HostedProvider(settings, "author")
    seen = []

    def fake_call(system, prompt, *, model, response_format, max_tokens, temperature):
        seen.append(response_format)
        return CandidatePassageDraft(
            orientation_en="You will read a public announcement about evening courses.",
            passage_ru="В центре открылись вечерние курсы. Заявки принимают до пятницы.",
            genre="announcement",
            topic="education",
            subtopic="courses",
            target_ilr="1",
            register="neutral",
            text_mode="notice",
            discourse_features=["purpose and deadline"],
            vocabulary_features=["routine public vocabulary"],
            provisional_difficulty=-0.5,
        ).model_dump_json(by_alias=True)

    monkeypatch.setattr(provider, "_call_hf", fake_call)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.target_ilr == "1"
    assert seen[0]["type"] == "json_schema"
    assert seen[0]["json_schema"]["strict"] is True


def test_legacy_genai_provider_and_hf_provider_are_preserved(monkeypatch, tmp_path):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    monkeypatch.setenv("GENAI_PROVIDER", "groq_then_hf")
    monkeypatch.setenv("HF_PROVIDER", "novita")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.generation_provider == "groq_then_hf"
        assert settings.hf_provider == "novita"
    finally:
        get_settings.cache_clear()


def test_deprecated_groq_model_produces_startup_warning():
    settings = Settings(groq_model="llama-3.3-70b-versatile")
    warnings = settings.model_warnings()
    assert warnings and "2026-08-16" in warnings[0]


def test_api_secrets_are_redacted_from_quarantine(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    settings = _settings(tmp_path).model_copy(update={"hf_token": "secret-hf-token"})
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    service = LiveGenerationService(settings, bank, project_root, provider=MockProvider())
    service._quarantine({"error": "Authorization token=secret-hf-token"})
    text = (tmp_path / "quarantine/live_generation_failures.jsonl").read_text(encoding="utf-8")
    assert "pipeline_version" in text
    assert "secret-hf-token" not in text
    assert "[REDACTED]" in text

class RepairingMock(RecordingMock):
    def __init__(self):
        super().__init__()
        self.passage_calls = 0

    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        if schema is CandidatePassageDraft:
            self.passage_calls += 1
            if self.passage_calls == 1:
                self.calls.append((system, prompt, schema.__name__))
                self.usage.add(20, 20)
                return CandidatePassageDraft(
                    orientation_en="You will read a short public announcement.",
                    passage_ru="Короткий текст.",
                    genre="announcement",
                    topic="education",
                    subtopic="courses",
                    target_ilr="2",
                    register="neutral",
                    text_mode="announcement",
                    discourse_features=["single statement"],
                    vocabulary_features=["routine vocabulary"],
                    provisional_difficulty=0.5,
                )
        return super().generate_json(
            system, prompt, schema, max_tokens=max_tokens, temperature=temperature
        )


class AlwaysFailProvider(AuthoringProvider):
    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        self.usage.add(5, 0)
        raise RuntimeError("provider token=top-secret-value failed")


def test_failed_candidate_is_repaired_and_repair_count_is_persisted(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    author = RepairingMock()
    verifier = RecordingMock()
    service = LiveGenerationService(
        _settings(tmp_path), bank, project_root, provider=author, verifier_provider=verifier
    )

    result = service.generate_and_store(
        skill="reading", level="2", mode="training", topics=[], competencies=[], maximum_questions=2
    )

    assert result.repair_count == 1
    assert result.passage.generation.repair_count == 1
    assert any("Validation issues" in prompt for _, prompt, schema in author.calls if schema == CandidatePassageDraft.__name__)


def test_smart_audit_skips_only_low_risk_reading_training(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    author = RecordingMock()
    verifier = RecordingMock()
    settings = _settings(tmp_path).model_copy(update={"generation_audit_mode": "smart"})
    service = LiveGenerationService(settings, bank, project_root, provider=author, verifier_provider=verifier)

    service.generate_and_store(
        skill="reading", level="1", mode="training", topics=[], competencies=[], maximum_questions=2
    )

    verifier_schemas = [schema for _, _, schema in verifier.calls]
    assert PassageAudit.__name__ not in verifier_schemas
    assert BlindVerificationBatch.__name__ in verifier_schemas


def test_provider_attempt_cap_prevents_runaway_fallback_calls(monkeypatch):
    settings = Settings(
        generation_provider="huggingface",
        hf_token="not-a-real-key",
        provider_max_retries=6,
        max_provider_attempts_per_stage=2,
    )
    provider = HostedProvider(settings)
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs.get("response_format"))
        raise RuntimeError("unsupported")

    monkeypatch.setattr(provider, "_call_hf", fail)
    with pytest.raises(Exception, match="Stage request cap"):
        provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert len(calls) == 2


def test_failed_provider_calls_are_attached_to_error_and_redacted(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    settings = _settings(tmp_path).model_copy(update={"hf_token": "top-secret-value"})
    service = LiveGenerationService(settings, bank, project_root, provider=AlwaysFailProvider())

    with pytest.raises(RuntimeError) as caught:
        service.generate_and_store(
            skill="reading", level="2", mode="training", topics=[], competencies=[], maximum_questions=2
        )

    assert getattr(caught.value, "request_count", 0) == 1
    quarantine = (tmp_path / "quarantine/live_generation_failures.jsonl").read_text(encoding="utf-8")
    assert "top-secret-value" not in quarantine
    assert "[REDACTED]" in quarantine


def test_settings_serialization_excludes_api_secrets():
    settings = Settings(hf_token="hf-secret", groq_api_key="groq-secret")
    dumped = settings.model_dump()
    assert "hf_token" not in dumped
    assert "groq_api_key" not in dumped


class ParaphrasingBatchVerifier(AuthoringProvider):
    """Returns the correct blind answers but paraphrases its supporting quote."""

    def __init__(self, correct_by_stem: dict[str, str]):
        super().__init__()
        self.correct_by_stem = correct_by_stem

    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        self.usage.add(10, 10)
        assert schema is BlindVerificationBatch
        marker = prompt.split("<ITEMS_JSON>", 1)[1].split("</ITEMS_JSON>", 1)[0]
        items = json.loads(marker.strip())
        verifications = []
        from core.generation import BlindVerificationBatchItem
        for item in items:
            correct_text = self.correct_by_stem[item["stem_en"]]
            selected = item["choices"].index(correct_text)
            verifications.append(BlindVerificationBatchItem(
                question_index=item["question_index"],
                selected_index=selected,
                second_best_index=-1,
                confidence=0.97,
                multiple_plausible=False,
                requires_outside_knowledge=False,
                evidence_sufficient=True,
                reasoning_match=True,
                answer_leakage=False,
                evidence_quote_ru="В сообщении говорится о вечерних занятиях для взрослых.",
                explanation="The selected answer is supported, although the evidence was paraphrased.",
            ))
        return BlindVerificationBatch(verifications=verifications)


def test_batched_verifier_paraphrase_does_not_discard_supported_questions(project_root):
    bank = ItemBank([project_root / "data/starter_items.jsonl"]).load()
    passage = bank.get_passage("r001")
    questions = bank.get_questions("r001")[:2]

    correct_by_stem = {
        question.stem_en: question.choices[question.correct_key]
        for question in questions
    }
    reports = validate_with_blind_verifier_batch(
        ParaphrasingBatchVerifier(correct_by_stem), passage, questions
    )

    assert len(reports) == 2
    assert all(report.status == "accepted" for report in reports)
    assert all(report.validator_scores["verifier_evidence_exact"] == 0.0 for report in reports)
    assert all("verifier_evidence_not_in_passage" not in report.failure_reasons for report in reports)


def test_operational_question_evidence_still_requires_exact_passage_support(project_root):
    bank = ItemBank([project_root / "data/starter_items.jsonl"]).load()
    passage = bank.get_passage("r001")
    question = bank.get_questions("r001")[0].model_copy(
        update={"evidence_ru": "Этой цитаты в исходном тексте нет."}
    )

    from core.validation import validate_question

    report = validate_question(question, passage)
    assert report.status == "rejected"
    assert "evidence_in_passage" in report.failure_reasons


class FullPipelineParaphrasingVerifier(MockProvider):
    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        result = super().generate_json(
            system, prompt, schema, max_tokens=max_tokens, temperature=temperature
        )
        if schema is BlindVerificationBatch:
            return result.model_copy(update={
                "verifications": [
                    item.model_copy(update={
                        "evidence_quote_ru": "Источник сообщает о курсах, сроках и условиях участия."
                    })
                    for item in result.verifications
                ]
            })
        return result


def test_full_generation_accepts_supported_bundle_when_verifier_paraphrases_evidence(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank(
        [project_root / "data/starter_items.jsonl", generated_path],
        writable_path=generated_path,
    ).load()
    service = LiveGenerationService(
        _settings(tmp_path),
        bank,
        project_root,
        provider=RecordingMock(),
        verifier_provider=FullPipelineParaphrasingVerifier(),
    )

    result = service.generate_and_store(
        skill="reading",
        level="2",
        mode="training",
        topics=["education"],
        competencies=["main idea", "prominent detail"],
        maximum_questions=2,
    )

    assert result.passage.id in bank.passages
    assert result.repair_count == 0
    assert all(report.status == "accepted" for report in result.question_reports)
    assert all(report.validator_scores["verifier_evidence_exact"] == 0.0 for report in result.question_reports)


class TargetedQuestionRepairProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.question_prompts: list[str] = []

    def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
        if schema is CandidateQuestionSet:
            self.question_prompts.append(prompt)
            if "Repair only these failed questions" in prompt:
                return CandidateQuestionSet(questions=[
                    {
                        "stem_en": "When must an applicant submit the registration form?",
                        "choices": ["By Friday", "By Tuesday morning", "After the first month", "Only after receiving an email"],
                        "proposed_correct_index": 0,
                        "rationale_en": "The announcement explicitly requires applications to be submitted by Friday.",
                        "evidence_ru": "Заявку необходимо отправить через сайт центра до пятницы",
                        "question_type": "prominent detail",
                    }
                ])
            base = super().generate_json(system, prompt, schema, max_tokens=max_tokens, temperature=temperature)
            questions = list(base.questions[:2])
            questions[1] = questions[1].model_copy(update={
                "choices": ["By Friday", "By Friday only", "After the first month", "Only after receiving an email"],
            })
            return CandidateQuestionSet(questions=questions)
        return super().generate_json(system, prompt, schema, max_tokens=max_tokens, temperature=temperature)


def test_only_failed_question_is_repaired_before_listening_tts(project_root, tmp_path, monkeypatch):
    generated_path = tmp_path / "generated.jsonl"
    bank = ItemBank([project_root / "data/starter_items.jsonl", generated_path], writable_path=generated_path).load()
    author = TargetedQuestionRepairProvider()
    verifier = MockProvider()

    def fake_tts(transcript, cache_dir, **kwargs):
        target = Path(cache_dir) / "targeted-repair.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ID3" + b"x" * 2048)
        return target

    monkeypatch.setattr("core.generation.generate_cached_tts", fake_tts)
    monkeypatch.setattr("core.generation.audio_duration_seconds", lambda path: 32.0)
    settings = _settings(tmp_path).model_copy(update={"generation_repair_attempts": 2})
    service = LiveGenerationService(settings, bank, project_root, provider=author, verifier_provider=verifier)

    result = service.generate_and_store(
        skill="listening", level="2", mode="training", topics=["education"],
        competencies=["main idea", "prominent detail"], maximum_questions=2,
    )

    assert result.repair_count == 1
    assert result.audio_asset is not None
    assert Path(result.audio_asset.path).exists()
    assert bank.get_passage(result.passage.id).audio_asset_id == result.audio_asset.id
    assert any("Repair only these failed questions: Q2" in prompt for prompt in author.question_prompts)
    assert result.questions[0].stem_en == "What is the main purpose of the announcement?"
    assert result.questions[1].stem_en == "When must an applicant submit the registration form?"
