from __future__ import annotations

import json

from core.config import Settings, get_settings
from core.generation import AUTHORING_SYSTEM, CandidatePassageDraft, CandidateQuestionSet, GeminiRuntimeState, HostedProvider


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


def test_gemini_http_payload_uses_current_response_format_and_model_discovery():
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-3.6-flash",
    )
    provider = HostedProvider(settings, "author")
    captured = {}

    class FakeResponse:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = json.dumps(self._payload)

        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            captured["list_path"] = path
            captured["list_params"] = params
            return FakeResponse(200, {
                "models": [
                    {
                        "name": "models/gemini-3.6-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                ]
            })

        def post(self, path, json):
            captured["path"] = path
            captured["json"] = json
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
            })

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidateQuestionSet, "strict", "gemini")
    text = provider._call_gemini(
        AUTHORING_SYSTEM,
        "Target ILR: 1",
        model="gemini-3.6-flash",
        response_format=fmt,
        max_tokens=1200,
        temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert captured["list_path"] == "/v1beta/models"
    assert captured["path"] == "/v1beta/models/gemini-3.6-flash:generateContent"
    config = captured["json"]["generationConfig"]
    assert config["maxOutputTokens"] == 1200
    assert config["responseFormat"]["text"]["mimeType"] == "application/json"
    schema = config["responseFormat"]["text"]["schema"]
    assert schema["type"] == "object"
    assert "responseMimeType" not in config
    assert "responseJsonSchema" not in config
    assert "maxItems" not in json.dumps(schema)
    assert "$defs" not in schema
    assert provider.usage.calls == 1
    assert provider.usage.input_tokens == 100
    assert provider.usage.output_tokens == 50


def test_gemini_discovery_skips_unavailable_configured_model_without_404_loop():
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-flash",
    )
    provider = HostedProvider(settings, "author")
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            return FakeResponse(200, {
                "models": [
                    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                ]
            })

        def post(self, path, json):
            calls.append(path)
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {},
            })

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "gemini")
    text = provider._call_gemini(
        AUTHORING_SYSTEM, "Target ILR: 1", model="gemini-2.5-flash",
        response_format=fmt, max_tokens=1200, temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert calls == ["/v1beta/models/gemini-3.5-flash-lite:generateContent"]
    assert provider.last_model == "gemini-3.5-flash-lite"


def test_gemini_model_discovery_reports_key_rejection_clearly():
    settings = Settings(generation_provider="gemini", gemini_api_key="bad-test")
    provider = HostedProvider(settings, "author")

    class FakeResponse:
        status_code = 403
        text = ""
        def json(self):
            return {"error": {"message": "API key does not have permission to use the Gemini API"}}

    class FakeClient:
        def get(self, path, params=None):
            return FakeResponse()

    provider._gemini = FakeClient()
    try:
        provider._discover_gemini_models()
        assert False, "expected ProviderError"
    except Exception as exc:
        assert "API key/project was rejected" in str(exc)
        assert "403" in str(exc)



def test_gemini_runtime_discovery_uses_actual_user_catalog_not_stale_36_default():
    """Regression for the Aug-2026 Space log: catalog had 2.5 Flash, not 3.6."""
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-3.6-flash",
    )
    provider = HostedProvider(settings, "author")
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            return FakeResponse(200, {
                "models": [
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                ]
            })

        def post(self, path, json):
            calls.append((path, json))
            assert path == "/v1beta/models/gemini-3.1-flash-lite:generateContent"
            config = json["generationConfig"]
            assert config["responseMimeType"] == "application/json"
            assert "responseJsonSchema" in config
            assert "responseFormat" not in config
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {},
            })

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "gemini")
    text = provider._call_gemini(
        AUTHORING_SYSTEM,
        "Target ILR: 1",
        model="gemini-3.6-flash",
        response_format=fmt,
        max_tokens=1200,
        temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert len(calls) == 1
    assert provider.last_model == "gemini-3.1-flash-lite"


def test_gemini_400_schema_compatibility_retries_alternate_format_before_groq():
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-flash",
    )
    provider = HostedProvider(settings, "author")
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            return FakeResponse(200, {
                "models": [
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                ]
            })

        def post(self, path, json):
            calls.append(json["generationConfig"])
            if len(calls) == 1:
                return FakeResponse(400, {"error": {"message": "Unknown name responseJsonSchema"}})
            assert "responseFormat" in json["generationConfig"]
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {},
            })

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "gemini")
    text = provider._call_gemini(
        AUTHORING_SYSTEM,
        "Target ILR: 1",
        model="gemini-2.5-flash",
        response_format=fmt,
        max_tokens=1200,
        temperature=0.2,
    )
    assert json.loads(text)["target_ilr"] == "1"
    assert len(calls) == 2


def test_gemini_remembers_retired_model_and_reuses_working_runtime_model():
    settings = Settings(
        generation_provider="gemini",
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-flash",
    )
    provider = HostedProvider(settings, "author")
    gets = []
    posts = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            gets.append(path)
            return FakeResponse(200, {
                "models": [
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                ]
            })

        def post(self, path, json):
            posts.append(path)
            if "gemini-2.5-flash:" in path:
                return FakeResponse(404, {"error": {"message": "This model is no longer available to new users."}})
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {},
            })

    provider._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "gemini")
    provider._call_gemini(
        AUTHORING_SYSTEM, "Target ILR: 1", model="gemini-2.5-flash",
        response_format=fmt, max_tokens=1200, temperature=0.2,
    )
    provider._call_gemini(
        AUTHORING_SYSTEM, "Target ILR: 1", model="gemini-2.5-flash",
        response_format=fmt, max_tokens=1200, temperature=0.2,
    )
    assert posts == [
        "/v1beta/models/gemini-2.5-flash:generateContent",
        "/v1beta/models/gemini-3.1-flash-lite:generateContent",
        "/v1beta/models/gemini-3.1-flash-lite:generateContent",
    ]
    assert gets == ["/v1beta/models"]
    assert provider._gemini_runtime.preferred_model == "gemini-3.1-flash-lite"


def test_gemini_runtime_model_memory_is_shared_across_pipeline_adapters():
    settings = Settings(
        generation_provider="gemini_then_groq",
        gemini_api_key="gemini-test",
        groq_api_key="groq-test",
        gemini_model="gemini-2.5-flash",
        gemini_verifier_model="gemini-2.5-flash",
    )
    shared = GeminiRuntimeState()
    author = HostedProvider(settings, "author", gemini_runtime_state=shared)
    verifier = HostedProvider(settings, "verifier", gemini_runtime_state=shared)
    gets: list[str] = []
    posts: list[str] = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
        def json(self):
            return self._payload

    class FakeClient:
        def get(self, path, params=None):
            gets.append(path)
            return FakeResponse(200, {
                "models": [
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                ]
            })

        def post(self, path, json):
            posts.append(path)
            if "gemini-2.5-flash:" in path:
                return FakeResponse(404, {"error": {"message": "This model is no longer available to new users."}})
            return FakeResponse(200, {
                "candidates": [{"content": {"parts": [{"text": _passage_json()}]}}],
                "usageMetadata": {},
            })

    author._gemini = FakeClient()
    verifier._gemini = FakeClient()
    fmt = HostedProvider._response_format(CandidatePassageDraft, "strict", "gemini")
    author._call_gemini(
        AUTHORING_SYSTEM, "Target ILR: 1", model="gemini-2.5-flash",
        response_format=fmt, max_tokens=1200, temperature=0.2,
    )
    verifier._call_gemini(
        AUTHORING_SYSTEM, "Target ILR: 1", model="gemini-2.5-flash",
        response_format=fmt, max_tokens=1200, temperature=0.0,
    )

    assert gets == ["/v1beta/models"]
    assert posts == [
        "/v1beta/models/gemini-2.5-flash:generateContent",
        "/v1beta/models/gemini-3.1-flash-lite:generateContent",
        "/v1beta/models/gemini-3.1-flash-lite:generateContent",
    ]
    assert shared.preferred_model == "gemini-3.1-flash-lite"
    assert "gemini-2.5-flash" in shared.rejected_models


def test_default_gemini_model_is_current_low_latency_flash_lite():
    settings = Settings()
    assert settings.gemini_model == "gemini-3.1-flash-lite"
    assert settings.gemini_verifier_model == "gemini-3.1-flash-lite"
