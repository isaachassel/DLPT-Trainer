"""Mandarin generation routing and authorization checks; never calls a paid API."""
import json
import httpx
import pytest
from core.content_workshop import Workshop
from core.dialogue_authoring import DialogueDraft, materialize
from core.elevenlabs import ElevenLabs
from core.preset_bank import ContentPackage, ROOT, read_package
from tests.test_preset_workshop import FakeProvider, KEY, MOCK_AUDIO, VOICES


class MandarinProvider(FakeProvider):
    def dialogue(self, turns, voices, model, language="ru"):
        self.calls.append(language)
        return MOCK_AUDIO


@pytest.fixture
def mandarin_work(tmp_path):
    work = Workshop(tmp_path / "mandarin")
    items = [i for i in read_package(ROOT / "data/pilots/mandarin_range_expansion.json").items if i.turns]
    work.edit(ContentPackage(items=items).model_dump_json())
    work.configure(KEY, MandarinProvider)
    return work


def test_mandarin_payload_maps_project_code_to_provider_code(mandarin_work):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, content=MOCK_AUDIO)
    client = ElevenLabs(KEY, httpx.MockTransport(handler))
    turns = mandarin_work.package.items[-1].turns
    client.dialogue(turns, VOICES, "eleven_v3", language="zh-CN")
    assert calls[0]["language_code"] == "zh"
    assert calls[0]["inputs"][0]["text"] == turns[0].text
    with pytest.raises(ValueError):
        client.dialogue(turns, VOICES, "eleven_v3", language="unsupported")
    assert len(calls) == 1


def test_owner_method_grant_is_language_specific_and_does_not_approve_content(mandarin_work):
    w = mandarin_work
    with pytest.raises(ValueError, match="pilot"):
        w.preflight("eleven_v3", VOICES, 4000, "batch")
    w.authorize_audio_method("TEST owner", "Extend demonstrated method to Mandarin", model="eleven_v3", voices=VOICES)
    assert w.ledger["pilot_approval"] is None  # no fabricated listening review
    plan = w.preflight("eleven_v3", VOICES, 4000, "batch")
    assert plan["language"] == "zh-CN"
    assert plan["characters_this_run"] == sum(len(t.text) for i in w.package.items for t in i.turns)
    with pytest.raises(ValueError, match="budget"):
        w.preflight("eleven_v3", VOICES, 1, "batch")
    w.preflight("eleven_v3", VOICES, 4000, "batch")
    assert "Saved 14" in w.generate()
    assert w.client.calls == ["zh-CN"] * 14
    assert all(i.review.status == "draft" for i in w.package.items)
    assert len(w.ledger["audio_reviews"]) == 14
    resumed = Workshop(w.directory)
    resumed.configure(KEY, MandarinProvider)
    assert resumed.preflight("eleven_v3", VOICES, 4000, "batch")["characters_this_run"] == 0
    resumed.ledger["automatic_audio_policy"]["language"] = "ru"
    with pytest.raises(ValueError, match="pilot"):
        resumed.preflight("eleven_v3", VOICES, 4000, "batch")


def test_mixed_language_and_incompatible_model_block_before_spending(mandarin_work):
    w = mandarin_work
    w.catalog["models"][0]["languages"] = [{"language_id": "ru"}]
    with pytest.raises(ValueError, match="does not support"):
        w.preflight("eleven_v3", VOICES, 4000)
    w.catalog["models"][0]["languages"] = [{"language_id": "zh"}]
    russian = read_package(ROOT / "data/pilots/russian_0plus_dialogues.json").items[0]
    w.package.items.append(russian)
    with pytest.raises(ValueError, match="one supported language"):
        w.preflight("eleven_v3", VOICES, 4000)
    assert w.ledger["spent_characters"] == 0 and not w.client.calls


def test_audition_and_edit_materialization_preserve_mandarin(mandarin_work):
    w = mandarin_work
    plan = w.preflight("eleven_v3", VOICES, 4000, "audition")
    assert plan["language"] == "zh-CN"
    assert all("你好" in t["text"] for t in plan["scripts"][0]["turns"])
    w.generate()
    assert w.client.calls == ["zh-CN"]
    prior = w.package.items[-1]
    draft = DialogueDraft(topic=prior.passage.topic, orientation_en=prior.passage.orientation_en,
        speakers=prior.speakers, turns=prior.turns,
        questions=[{k: getattr(q, k) for k in ("stem_en", "choices", "correct_key", "rationale_en", "evidence_ru")}
                   for q in prior.questions])
    edited = materialize(draft, prior.id, language=prior.passage.language, target_ilr=prior.passage.target_ilr)
    assert edited.passage.language == "zh-CN" and edited.passage.target_ilr == "3"
    assert edited.passage.word_count == prior.passage.word_count
    assert all(q.target_ilr == "3" for q in edited.questions)


def test_russian_paid_fingerprints_unchanged_on_upgrade(tmp_path):
    import hashlib
    w = Workshop(tmp_path / "russian")
    i = w.package.items[0]
    before = [i.id, i.content_version, [t.model_dump() for t in i.turns], "eleven_v3", VOICES]
    assert w._fingerprint(i, "eleven_v3", VOICES) == hashlib.sha256(json.dumps(before, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert w._config("eleven_v3", VOICES) == hashlib.sha256(json.dumps(["eleven_v3", VOICES], sort_keys=True).encode()).hexdigest()
