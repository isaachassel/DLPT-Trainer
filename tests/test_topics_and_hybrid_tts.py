from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.audio import _dialogue_speaker_profiles, generate_cached_tts, split_speaker_turns
from core.config import Settings
from core.generation import AUTHORING_SYSTEM, CandidatePassageDraft, HostedProvider, ProviderError
from core.topics import CANONICAL_TOPICS, canonicalize_topic, choose_balanced_topic, normalize_requested_topics
from ui.callbacks import topic_controls


def _passage_json(topic: str = "Education") -> str:
    return CandidatePassageDraft(
        orientation_en="You will read a public notice about evening courses.",
        passage_ru=(
            "В городском центре открылись вечерние курсы для взрослых. "
            "Занятия проходят два раза в неделю, а заявки принимают до пятницы. "
            "Организаторы сообщили, что число мест ограничено и регистрация проводится через сайт."
        ),
        genre="announcement",
        topic=topic,
        subtopic="evening courses",
        target_ilr="1",
        register="neutral",
        text_mode="notice",
        discourse_features=["purpose and deadline"],
        vocabulary_features=["routine public vocabulary"],
        provisional_difficulty=-0.5,
    ).model_dump_json(by_alias=True)


def test_generated_subtopics_collapse_into_stable_dlpt_taxonomy():
    examples = {
        "city infrastructure – bike lanes": "Transportation",
        "urban transportation / bike sharing program": "Transportation",
        "public-policy / transportation": "Transportation",
        "utility outage": "Public services",
        "utility service disruption": "Public services",
        "community service announcement": "Public services",
        "public-service announcement about city park wi-fi": "Public services",
        "municipal waste management": "Environment",
        "opening of a new public library": "Culture and society",
        "local community center announces a free art class for children": "Education",
        "package delivery": "Commerce",
        "healthcare infrastructure": "Public health",
    }
    assert {source: canonicalize_topic(source) for source in examples} == examples


def test_requested_topic_normalization_deduplicates_transport_variants():
    assert normalize_requested_topics([
        "Transportation",
        "transportation",
        "urban transportation / bike sharing program",
        "Education",
    ]) == ["Transportation", "Education"]


def test_balanced_topic_selection_strongly_avoids_recent_transportation():
    selected = choose_balanced_topic(
        requested_topics=[],
        existing_topics=["Transportation"] * 7 + ["Education", "Public health"],
        recent_topics=["Transportation", "Transportation", "Transportation"],
        nonce="topic-balance-regression",
    )
    assert selected != "Transportation"
    assert selected in CANONICAL_TOPICS


def test_topic_selector_never_exposes_generated_subtopic_clutter():
    choices = topic_controls("Listening", ["urban transportation / bike sharing program"])["choices"]
    assert choices == list(CANONICAL_TOPICS)
    assert "urban transportation / bike sharing program" not in choices
    assert "city infrastructure – bike lanes" not in choices


def test_provider_quota_cooldown_skips_hf_on_following_stage(monkeypatch):
    settings = Settings(
        generation_provider="hf_then_groq",
        hf_token="hf-test",
        groq_api_key="groq-test",
        provider_max_retries=0,
        max_provider_attempts_per_stage=4,
        structured_output_mode="strict",
    )
    provider = HostedProvider(settings, "author")
    calls: list[str] = []

    def fail_hf(*args, **kwargs):
        calls.append("hf")
        raise RuntimeError("402 Payment Required")

    def succeed_groq(*args, **kwargs):
        calls.append("groq")
        return _passage_json()

    monkeypatch.setattr(provider, "_call_hf", fail_hf)
    monkeypatch.setattr(provider, "_call_groq", succeed_groq)

    provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert calls == ["hf", "groq", "groq"]


def test_quota_failure_does_not_retry_same_provider_in_weaker_modes(monkeypatch):
    settings = Settings(
        generation_provider="huggingface",
        hf_token="hf-test",
        provider_max_retries=1,
        max_provider_attempts_per_stage=8,
        structured_output_mode="auto",
        allow_plain_json_fallback=True,
    )
    provider = HostedProvider(settings, "author")
    calls = 0

    def fail_hf(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("402 Payment Required")

    monkeypatch.setattr(provider, "_call_hf", fail_hf)
    with pytest.raises(ProviderError):
        provider.generate_json(AUTHORING_SYSTEM, "Target ILR: 1", CandidatePassageDraft)
    assert calls == 1


def test_piper_voice_dispatch_is_separate_from_edge_worker(monkeypatch, tmp_path):
    import core.audio as audio

    calls: list[tuple[str, str]] = []

    def fake_piper(text, voice_id, rate, volume, output_mp3, model_root, timeout_seconds):
        calls.append((voice_id, text))
        output_mp3.write_bytes(b"ID3" + b"0" * 2048)

    def forbidden_edge(*args, **kwargs):
        raise AssertionError("Edge worker must not be used for a Piper voice")

    monkeypatch.setattr(audio, "_piper_tts_save", fake_piper)
    monkeypatch.setattr(audio, "_edge_tts_save", forbidden_edge)
    output = generate_cached_tts(
        "Добрый вечер.",
        tmp_path,
        voice="piper:ru_RU-irina-medium",
        engine_version="piper-dispatch-test-v1",
    )
    assert output.exists()
    assert calls == [("piper:ru_RU-irina-medium", "Добрый вечер.")]


def test_four_speakers_receive_four_free_voice_profiles_before_reuse():
    turns = split_speaker_turns(
        "Ведущий: Первый вопрос.\nГость: Первый ответ.\n"
        "Эксперт: Комментарий.\nКорреспондент: Дополнение."
    )
    profiles = _dialogue_speaker_profiles(turns, "ru-RU-DmitryNeural", "ru", base_rate="+0%")
    voices = [profiles[key].voice for key in ("ведущий", "гость", "эксперт", "корреспондент")]
    assert voices == [
        "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural",
        "piper:ru_RU-irina-medium",
        "piper:ru_RU-ruslan-medium",
    ]


def test_provider_rate_limit_cooldown_is_shared_across_generation_stages(tmp_path):
    import threading
    from core.generation import HostedProvider
    from core.config import Settings

    shared = {}
    lock = threading.RLock()
    settings = Settings(
        generation_provider="hf_then_groq",
        verification_provider="auto",
        hf_token="hf-test",
        groq_api_key="groq-test",
    )
    author = HostedProvider(settings, "author", cooldown_state=shared, cooldown_lock=lock)
    verifier = HostedProvider(settings, "verifier", cooldown_state=shared, cooldown_lock=lock)

    author._mark_provider_cooldown("groq", "provider rate limit reached")

    assert "groq" not in verifier._provider_order()
    assert verifier.cooldown_remaining()["groq"] >= 89


def test_retry_after_and_reset_headers_are_parsed_for_cooldown():
    from types import SimpleNamespace
    from core.generation import HostedProvider

    exc = RuntimeError("429 Too Many Requests")
    exc.response = SimpleNamespace(headers={
        "retry-after": "4",
        "x-ratelimit-reset-tokens": "1m17.5s",
    })
    assert HostedProvider._retry_delay_from_exception(exc) == 77.5
