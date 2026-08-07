from __future__ import annotations

import json

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


def test_gemini_is_promoted_ahead_of_legacy_hf_groq_space(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "hf_then_groq")
    monkeypatch.setenv("HF_TOKEN", "hf-bank-token")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    monkeypatch.delenv("ENABLE_HF_INFERENCE", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        provider = HostedProvider(settings, "author")
        assert settings.enable_hf_inference is False
        assert provider._provider_order() == ["gemini", "groq"]
        assert settings.bank_token == "hf-bank-token"
    finally:
        get_settings.cache_clear()


def test_gemini_is_used_before_groq(monkeypatch):
    settings = Settings(
        generation_provider="gemini_then_groq",
        gemini_api_key="gemini-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="strict",
    )
    provider = HostedProvider(settings, "author")
    calls: list[str] = []

    def fake_gemini(*args, **kwargs):
        calls.append("gemini")
        return _passage_json()

    def fake_groq(*args, **kwargs):
        calls.append("groq")
        return _passage_json()

    monkeypatch.setattr(provider, "_call_gemini", fake_gemini)
    monkeypatch.setattr(provider, "_call_groq", fake_groq)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.target_ilr == "1"
    assert calls == ["gemini"]


def test_gemini_rate_limit_fails_over_to_groq(monkeypatch):
    settings = Settings(
        generation_provider="gemini_then_groq",
        gemini_api_key="gemini-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=2,
        structured_output_mode="strict",
    )
    provider = HostedProvider(settings, "author")
    calls: list[str] = []

    def fail_gemini(*args, **kwargs):
        calls.append("gemini")
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    def succeed_groq(*args, **kwargs):
        calls.append("groq")
        return _passage_json()

    monkeypatch.setattr(provider, "_call_gemini", fail_gemini)
    monkeypatch.setattr(provider, "_call_groq", succeed_groq)
    result = provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert result.passage_ru
    assert calls == ["gemini", "groq"]
    assert "gemini" in provider.cooldown_remaining()


def test_gemini_http_payload_uses_json_schema_and_zero_thinking():
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-flash",
    )
    provider = HostedProvider(settings, "author")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
            }

    class FakeClient:
        def post(self, path, json):
            captured["path"] = path
            captured["json"] = json
            return FakeResponse()

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidateQuestionSet, "strict", "gemini")
    text = provider._call_gemini(
        AUTHORING_SYSTEM,
        "Target ILR: 1",
        model="gemini-2.5-flash",
        response_format=fmt,
        max_tokens=1200,
        temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert captured["path"] == "/v1beta/models/gemini-2.5-flash:generateContent"
    config = captured["json"]["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingBudget": 0}
    assert config["responseFormat"]["text"]["mimeType"] == "application/json"
    assert config["responseFormat"]["text"]["schema"]["type"] == "object"
    assert provider.usage.calls == 1
    assert provider.usage.input_tokens == 100
    assert provider.usage.output_tokens == 50
