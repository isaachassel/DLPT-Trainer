from __future__ import annotations

import json

import pytest

from core.config import Settings
from core.generation import (
    AUTHORING_SYSTEM,
    BlindVerificationBatch,
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
    bank = ItemBank(project_root / "data/starter_items.jsonl").load()
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
    assert "Inference Providers permission" in str(caught.value)
    assert "hf-test" not in str(caught.value)
