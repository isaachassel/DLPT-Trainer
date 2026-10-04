from __future__ import annotations

import json

import pytest

from core.config import Settings
from core.generation import (
    AUTHORING_SYSTEM,
    BlindVerificationBatch,
    BlindVerificationBatchItem,
    CandidatePassageDraft,
    HostedProvider,
    MockProvider,
    validate_with_blind_verifier_batch,
)
from core.item_bank import ItemBank


def _passage_json() -> str:
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


def test_provider_failover_is_round_robin_before_weaker_modes(monkeypatch):
    settings = Settings(
        generation_provider="hf_then_groq",
        hf_token="hf-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="auto",
    )
    provider = HostedProvider(settings, "author")
    calls: list[tuple[str, str | None]] = []

    def fail_hf(*args, **kwargs):
        calls.append(("hf", kwargs["response_format"]["type"]))
        raise RuntimeError("HF route unavailable")

    def succeed_groq(*args, **kwargs):
        calls.append(("groq", kwargs["response_format"]["type"]))
        return _passage_json()

    monkeypatch.setattr(provider, "_call_hf", fail_hf)
    monkeypatch.setattr(provider, "_call_groq", succeed_groq)

    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.target_ilr == "1"
    assert calls == [("hf", "json_schema"), ("groq", "json_schema")]


def test_controlled_plain_json_fallback_accepts_one_complete_fenced_document(monkeypatch):
    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=4,
        structured_output_mode="auto",
        allow_plain_json_fallback=True,
    )
    provider = HostedProvider(settings, "author")
    modes: list[str | None] = []

    def fake_hf(*args, **kwargs):
        response_format = kwargs["response_format"]
        modes.append(None if response_format is None else response_format["type"])
        if response_format is not None:
            raise RuntimeError("structured mode unsupported")
        return "```json\n" + _passage_json() + "\n```"

    monkeypatch.setattr(provider, "_call_hf", fake_hf)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.target_ilr == "1"
    assert modes == ["json_schema", "json_schema", "json_object", None]


def test_plain_json_parser_does_not_extract_arbitrary_brace_substrings():
    with pytest.raises(Exception):
        HostedProvider._parse_structured_text(
            "prose before {\"target_ilr\": \"1\"} prose after",
            CandidatePassageDraft,
        )


def test_batched_verifier_hides_proposed_answers(project_root):
    bank = ItemBank(project_root / "tests/fixtures/legacy/starter_items.jsonl").load()
    passage = bank.get_passage("r001")
    questions = bank.get_questions("r001")[:2]

    class RecordingBatchMock(MockProvider):
        def __init__(self):
            super().__init__()
            self.prompt = ""

        def generate_json(self, system, prompt, schema, *, max_tokens=None, temperature=None):
            if schema is BlindVerificationBatch:
                self.prompt = prompt
            return super().generate_json(system, prompt, schema, max_tokens=max_tokens, temperature=temperature)

    provider = RecordingBatchMock()
    reports = validate_with_blind_verifier_batch(provider, passage, questions)
    assert len(reports) == len(questions)
    lowered = provider.prompt.casefold()
    assert "correct_key" not in lowered
    assert "proposed_correct" not in lowered
    assert "proposed answer" in lowered  # only the statement that answers are hidden


def test_provider_error_message_explains_permission_problem(monkeypatch):
    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=1,
    )
    provider = HostedProvider(settings)

    def forbidden(*args, **kwargs):
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(provider, "_call_hf", forbidden)
    with pytest.raises(Exception) as caught:
        provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert "provider access is forbidden" in str(caught.value)
    assert "hf-test" not in str(caught.value)


def test_question_schema_enforces_exact_supported_types_and_omits_internal_metadata():
    from core.generation import CandidateQuestionSet

    schema = CandidateQuestionSet.model_json_schema()
    question_schema = schema["$defs"]["CandidateQuestion"]
    properties = question_schema["properties"]
    assert set(properties) == {
        "stem_en",
        "choices",
        "proposed_correct_index",
        "rationale_en",
        "evidence_ru",
        "question_type",
    }
    assert set(properties["question_type"]["enum"]) == {
        "main idea",
        "prominent detail",
        "inference",
        "speaker/writer intent",
        "tone or attitude",
        "reference",
        "sequence",
        "cause and effect",
        "relationship of ideas",
        "meaning from context",
    }
    assert "target_ilr" not in properties
    assert "provisional_difficulty" not in properties


def test_question_payload_normalizes_common_hosted_model_variants():
    from core.generation import CandidateQuestionSet

    payload = {
        "items": [
            {
                "question": "What is the main purpose of the announcement?",
                "options": {
                    "A": "To announce a new evening course",
                    "B": "To cancel all weekend classes",
                    "C": "To advertise a private apartment",
                    "D": "To report a transportation delay",
                },
                "correct_answer": "A",
                "explanation": "The announcement says that evening courses have opened.",
                "evidence_quote_ru": "открылись вечерние курсы",
                "type": "central idea",
                "target_ilr": "ILR 2",
                "difficulty": 0.8,
                "unused_model_note": "must be ignored",
            }
        ],
        "provider_note": "also ignored",
    }

    parsed = CandidateQuestionSet.model_validate(payload)
    question = parsed.questions[0]
    assert question.stem_en.startswith("What is the main purpose")
    assert question.choices[0].startswith("To announce")
    assert question.proposed_correct_index == 0
    assert question.question_type == "main idea"
    assert not hasattr(question, "target_ilr")
    assert not hasattr(question, "provisional_difficulty")


def test_hosted_provider_accepts_normalized_question_payload_on_first_attempt(monkeypatch):
    from core.generation import CandidateQuestionSet

    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=8,
        structured_output_mode="auto",
    )
    provider = HostedProvider(settings, "author")
    calls = []

    def fake_hf(*args, **kwargs):
        calls.append(kwargs["response_format"]["type"])
        return json.dumps({
            "questions": [{
                "stem": "What does the center announce?",
                "answer_choices": [
                    "It has opened evening courses.",
                    "It has closed the building.",
                    "It has canceled registration.",
                    "It has moved to another city.",
                ],
                "correct_answer": "A",
                "rationale": "The Russian source directly announces that evening courses have opened.",
                "evidence": "открылись вечерние курсы",
                "competency": "detail",
                "level": "2",
                "difficulty": 0.5,
            }]
        }, ensure_ascii=False)

    monkeypatch.setattr(provider, "_call_hf", fake_hf)
    result = provider.generate_json(AUTHORING_SYSTEM, "Create questions", CandidateQuestionSet)
    assert result.questions[0].question_type == "prominent detail"
    assert result.questions[0].proposed_correct_index == 0
    assert calls == ["json_schema"]


def test_question_validation_error_includes_field_location():
    from core.generation import CandidateQuestionSet

    bad = json.dumps({"questions": [{"stem_en": "Question?"}]})
    with pytest.raises(Exception) as caught:
        HostedProvider._parse_structured_text(bad, CandidateQuestionSet)
    message = str(caught.value)
    assert "questions.0.choices" in message
    assert "questions.0.proposed_correct_index" in message


def test_full_live_service_accepts_realistic_question_variants_and_persists(project_root, tmp_path, monkeypatch):
    from core.generation import CandidateQuestionSet, LiveGenerationService

    generated_path = tmp_path / "generated.jsonl"
    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="auto",
        generation_audit_mode="always",
        generation_repair_attempts=1,
        generated_item_bank_path=generated_path,
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
        session_dir=tmp_path / "sessions",
        history_dir=tmp_path / "history",
    )
    bank = ItemBank(
        [project_root / "tests/fixtures/legacy/starter_items.jsonl", generated_path], writable_path=generated_path
    ).load()
    author = HostedProvider(settings, "author")
    fixture = MockProvider()
    calls = []

    def fake_hf(system, prompt, **kwargs):
        calls.append(prompt)
        if "Create one original Russian" in prompt:
            return fixture.generate_json(system, prompt, CandidatePassageDraft).model_dump_json(by_alias=True)
        if "Create exactly" in prompt:
            base = fixture.generate_json(system, prompt, CandidateQuestionSet)
            payload = {"items": []}
            for question in base.questions:
                payload["items"].append({
                    "question": question.stem_en,
                    "options": {letter: text for letter, text in zip("ABCD", question.choices)},
                    "correct_answer": "ABCD"[question.proposed_correct_index],
                    "explanation": question.rationale_en,
                    "evidence_quote_ru": question.evidence_ru,
                    "type": "detail" if question.question_type == "prominent detail" else question.question_type,
                    "target_ilr": "ILR 2",
                    "difficulty": 0.7,
                    "provider_extra": "ignored",
                })
            return json.dumps(payload, ensure_ascii=False)
        raise AssertionError("Unexpected author prompt")

    monkeypatch.setattr(author, "_call_hf", fake_hf)
    service = LiveGenerationService(
        settings, bank, project_root, provider=author, verifier_provider=MockProvider()
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
    assert generated_path.exists()
    assert len(bank.get_questions(result.passage.id)) == 2
    assert all(question.target_ilr == "2" for question in bank.get_questions(result.passage.id))
    assert any("Create exactly" in prompt for prompt in calls)


def test_hf_bad_request_downgrades_structured_mode_for_following_stage(monkeypatch):
    from core.config import Settings
    from core.generation import CandidatePassageDraft, HostedProvider, MockProvider

    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        structured_output_mode="auto",
        max_provider_attempts_per_stage=4,
        provider_max_retries=0,
    )
    provider = HostedProvider(settings, "author")
    fixture = MockProvider().generate_json("", "", CandidatePassageDraft)
    calls = []

    def fake_hf(system, prompt, *, model, response_format, max_tokens, temperature):
        calls.append(response_format)
        strict = bool(
            response_format
            and response_format.get("type") == "json_schema"
            and response_format.get("json_schema", {}).get("strict") is True
        )
        if strict:
            raise RuntimeError("400 Bad Request")
        return fixture.model_dump_json()

    monkeypatch.setattr(provider, "_call_hf", fake_hf)
    result = provider.generate_json("system", "prompt", CandidatePassageDraft)
    assert result.passage_ru
    assert len(calls) == 2
    assert provider._response_modes("hf", settings.hf_text_model)[0] == "best_effort"


def _blind_batch_json() -> str:
    return BlindVerificationBatch(
        verifications=[
            BlindVerificationBatchItem(
                question_index=0,
                selected_index=0,
                second_best_index=-1,
                confidence=0.96,
                multiple_plausible=False,
                requires_outside_knowledge=False,
                evidence_sufficient=True,
                reasoning_match=True,
                answer_leakage=False,
                evidence_quote_ru="вечерние курсы",
                explanation="The first choice is directly supported by the source.",
            )
        ]
    ).model_dump_json()


def test_groq_blind_batch_schema_is_transport_safe_but_locally_strict():
    schema = HostedProvider._groq_schema(BlindVerificationBatch)
    encoded = json.dumps(schema)
    assert "minItems" not in encoded
    assert "maxItems" not in encoded
    assert '"title"' not in encoded
    assert schema["additionalProperties"] is False
    item = schema["$defs"]["BlindVerificationBatchItem"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])


def test_verifier_stays_on_groq_json_mode_after_batch_strict_400(monkeypatch):
    settings = Settings(
        generation_provider="gemini_then_groq",
        verification_provider="groq_then_gemini",
        gemini_api_key="gemini-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=4,
        structured_output_mode="auto",
        allow_plain_json_fallback=True,
    )
    provider = HostedProvider(settings, "verifier")
    groq_modes: list[str | None] = []
    gemini_calls: list[str] = []

    def fake_groq(*args, **kwargs):
        response_format = kwargs["response_format"]
        mode = None if response_format is None else response_format["type"]
        groq_modes.append(mode)
        if mode == "json_schema":
            raise RuntimeError("400 Bad Request: structured schema rejected")
        return _blind_batch_json()

    def fake_gemini(*args, **kwargs):
        gemini_calls.append("gemini")
        return _blind_batch_json()

    monkeypatch.setattr(provider, "_call_groq", fake_groq)
    monkeypatch.setattr(provider, "_call_gemini", fake_gemini)
    result = provider.generate_json(
        "Verify independently.",
        "Verify question 0.",
        BlindVerificationBatch,
        max_tokens=900,
        temperature=0.0,
    )

    assert result.verifications[0].question_index == 0
    assert groq_modes == ["json_schema", "json_object"]
    assert gemini_calls == []
    assert provider.last_provider == "groq"
    assert provider.last_mode == "json_object"
