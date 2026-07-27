from __future__ import annotations
import pytest
from core.config import Settings
from core.generation import HostedProvider, ProviderError


def test_missing_provider_keys_produce_useful_error():
    settings = Settings(generation_provider="huggingface", hf_token=None)
    ready, message = settings.provider_readiness()
    assert not ready and "key" in message.lower()


def test_provider_failure_does_not_mutate_session_state():
    settings = Settings(generation_provider="disabled")
    provider = HostedProvider(settings)
    marker = {"responses": 3}
    with pytest.raises(ProviderError, match="disabled"):
        provider.generate_json("x", "y", __import__('core.generation', fromlist=['CandidatePassage']).CandidatePassage)
    assert marker == {"responses": 3}


def test_space_auto_persistence_upgrades_legacy_local_backend(monkeypatch):
    from core.config import get_settings

    monkeypatch.setenv("SPACE_HOST", "alsubij-dlpt-trainer.hf.space")
    monkeypatch.setenv("HF_TOKEN", "write-capable-token")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("AUTO_PROVISION_DATASET_BANK", "true")
    get_settings.cache_clear()
    settings = get_settings()
    try:
        assert settings.storage_backend == "hybrid"
        assert settings.bank_token == "write-capable-token"
    finally:
        get_settings.cache_clear()
