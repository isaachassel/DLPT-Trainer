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
