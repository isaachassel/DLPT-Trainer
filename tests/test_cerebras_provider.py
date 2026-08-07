from __future__ import annotations

import json

import pytest

from core.config import Settings, get_settings
from core.generation import AUTHORING_SYSTEM, CandidatePassageDraft, CandidateQuestionSet, HostedProvider


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


def test_cerebras_is_first_free_generation_route_when_key_is_added_to_legacy_space(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "hf_then_groq")
    monkeypatch.setenv("HF_TOKEN", "hf-bank-token")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "cerebras-test")
    monkeypatch.setenv("PREFER_CEREBRAS_IF_AVAILABLE", "true")
    monkeypatch.setenv("PREFER_GEMINI_IF_AVAILABLE", "false")
    monkeypatch.delenv("ENABLE_HF_INFERENCE", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        provider = HostedProvider(settings, "author")
        # HF_TOKEN remains usable for the generated-bank mirror, but monthly HF
        # inference credits are not consumed unless explicitly enabled.
        assert settings.bank_token == "hf-bank-token"
        assert settings.enable_hf_inference is False
        assert provider._provider_order() == ["cerebras", "groq"]
    finally:
        get_settings.cache_clear()


def test_cerebras_strict_schema_removes_unsupported_array_constraints():
    fmt = HostedProvider._response_format(CandidateQuestionSet, "strict", "cerebras")
    assert fmt is not None
    text = json.dumps(fmt, separators=(",", ":"))
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert "minItems" not in text
    assert "maxItems" not in text
    assert '"additionalProperties":false' in text
    assert len(json.dumps(fmt["json_schema"]["schema"], separators=(",", ":"))) < 5000


def test_cerebras_provider_is_used_before_groq(monkeypatch):
    settings = Settings(
        generation_provider="cerebras_then_groq",
        cerebras_api_key="cerebras-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="strict",
    )
    provider = HostedProvider(settings, "author")
    calls: list[str] = []

    def fake_cerebras(*args, **kwargs):
        calls.append("cerebras")
        return _passage_json()

    def fake_groq(*args, **kwargs):
        calls.append("groq")
        return _passage_json()

    monkeypatch.setattr(provider, "_call_cerebras", fake_cerebras)
    monkeypatch.setattr(provider, "_call_groq", fake_groq)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.target_ilr == "1"
    assert calls == ["cerebras"]


def test_cerebras_rate_limit_fails_over_to_groq(monkeypatch):
    settings = Settings(
        generation_provider="cerebras_then_groq",
        cerebras_api_key="cerebras-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="strict",
    )
    provider = HostedProvider(settings, "author")
    calls: list[str] = []

    def fail_cerebras(*args, **kwargs):
        calls.append("cerebras")
        raise RuntimeError("429 Too Many Requests")

    def succeed_groq(*args, **kwargs):
        calls.append("groq")
        return _passage_json()

    monkeypatch.setattr(provider, "_call_cerebras", fail_cerebras)
    monkeypatch.setattr(provider, "_call_groq", succeed_groq)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.passage_ru
    assert calls == ["cerebras", "groq"]
    assert "cerebras" in provider.cooldown_remaining()


def test_cerebras_http_payload_uses_low_reasoning_and_strict_format():
    settings = Settings(
        generation_provider="cerebras",
        cerebras_api_key="cerebras-test",
        cerebras_model="gpt-oss-120b",
    )
    provider = HostedProvider(settings, "author")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": _passage_json()}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }

    class FakeClient:
        def post(self, path, json):
            captured["path"] = path
            captured["json"] = json
            return FakeResponse()

    provider._cerebras = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "cerebras")
    text = provider._call_cerebras(
        AUTHORING_SYSTEM,
        "Target ILR: 1",
        model="gpt-oss-120b",
        response_format=fmt,
        max_tokens=1200,
        temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["json"]["reasoning_effort"] == "low"
    assert captured["json"]["response_format"]["json_schema"]["strict"] is True
    assert provider.usage.calls == 1
    assert provider.usage.input_tokens == 100
    assert provider.usage.output_tokens == 50
