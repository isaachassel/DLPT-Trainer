"""No live credentials, paid calls or production review promotions in this suite."""
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from core.content_workshop import Workshop, PILOTS
from core.elevenlabs import ElevenLabs, ProviderError
from core.preset_bank import (ContentPackage, MANIFEST, PresetBank, ROOT, Review, local_asset,
                              read_package, write_package)
from core.validation import validate_passage, validate_question

KEY = "fixture-session-secret-not-a-real-key"
VOICES = {"A": "russian-a", "B": "russian-b"}
MOCK_AUDIO = b"ID3" + b"TEST ONLY NOT REAL SPEECH" * 40


class FakeProvider:
    def __init__(self, key):
        self.calls = []
        self.fail_at = None
    def catalog(self):
        return {"account": {"tier": "TEST ONLY"}, "models": [{"model_id": "eleven_v3"}],
                "voices": [{"voice_id": v, "name": v} for v in VOICES.values()]}
    def dialogue(self, turns, voices, model):
        self.calls.append((turns, voices, model))
        if len(self.calls) == self.fail_at:
            raise ProviderError("TEST timeout", uncertain=True)
        return MOCK_AUDIO


@pytest.fixture
def workshop(tmp_path):
    work = Workshop(tmp_path / "private")
    work.configure(KEY, FakeProvider)
    return work


def pilot(work):
    plan = work.preflight("eleven_v3", VOICES, 20000)
    assert len(plan["scripts"]) == 1
    assert "Saved 1" in work.generate()
    work.approve_voices()


def test_production_all_pending_and_pilots_original():
    assert {x.review.status for x in read_package(MANIFEST).items} == {"draft"}
    assert not PresetBank().load().active_passages("reading", "ru")
    package = read_package(PILOTS)
    assert len(package.items) == 12
    assert len({x.passage.content_hash for x in package.items}) == 12
    for item in package.items:
        assert item.review.status == "draft" and item.audio is None
        assert item.passage.target_ilr == "0+" and len(item.questions) == 2
        assert validate_passage(item.passage, item.questions).status == "accepted"
        assert all(validate_question(q, item.passage).status == "accepted" for q in item.questions)


def test_only_approved_content_and_separate_skills(approved_bank):
    assert approved_bank.active_passages("reading", "ru")
    assert approved_bank.active_passages("listening", "ru")
    assert all(p.skill == "reading" for p in approved_bank.active_passages("reading", "ru"))
    assert all(p.skill == "listening" for p in approved_bank.active_passages("listening", "ru"))
    with pytest.raises(PermissionError):
        approved_bank.append_validated_bundle(None, [])


def test_missing_and_changed_audio_excluded(tmp_path):
    package = read_package(MANIFEST)
    item = next(x for x in package.items if x.passage.skill == "listening")
    item.review = Review(status="approved", reviewer="TEST", reviewed_at="2026-10-03", reuse_attested=True)
    path = tmp_path / "bank.json"
    write_package(path, ContentPackage(items=[item]))
    bank = PresetBank(path, tmp_path).load()
    assert not bank.active_passages("listening", "ru") and bank.load_warnings
    destination = tmp_path / item.audio.path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(MOCK_AUDIO)
    bank = PresetBank(path, tmp_path).load()
    assert not bank.active_passages("listening", "ru")
    assert "checksum" in bank.load_warnings[0]


@pytest.mark.parametrize("change", ["duplicate", "level", "key", "reference"])
def test_bad_manifest_fails_closed(tmp_path, change):
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    item = data["items"][0]
    if change == "duplicate":
        data["items"].append(item)
    elif change == "level":
        item["passage"]["target_ilr"] = "4+"
    elif change == "key":
        item["questions"][0]["correct_key"] = "E"
    else:
        item["questions"][0]["passage_id"] = "unrelated"
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    bank = PresetBank(path).load()
    assert not bank.passages and bank.load_warnings


@pytest.mark.parametrize("path", ["../secret", "C:/secret", "https://host/audio.mp3", "..\\secret"])
def test_unsafe_asset_paths(tmp_path, path):
    with pytest.raises(ValueError):
        local_asset(tmp_path, path)


def test_pilot_gate_budget_and_no_duplicate_paid_submit(workshop):
    with pytest.raises(ValueError, match="pilot"):
        workshop.preflight("eleven_v3", VOICES, 20000, "batch")
    with pytest.raises(ValueError, match="budget"):
        workshop.preflight("eleven_v3", VOICES, 10)
    pilot(workshop)
    assert len(workshop.client.calls) == 1
    with pytest.raises(ValueError, match="preflight"):
        workshop.generate()
    workshop.preflight("eleven_v3", VOICES, 20000)
    assert "Saved 0" in workshop.generate()
    plan = workshop.preflight("eleven_v3", VOICES, 20000, "batch")
    assert len(plan["scripts"]) == 11
    assert "Saved 11" in workshop.generate()
    assert len(workshop.client.calls) == 12


def test_interrupted_batch_preserves_outputs_and_never_blindly_retries(workshop):
    pilot(workshop)
    workshop.client.fail_at = 3
    workshop.preflight("eleven_v3", VOICES, 20000, "batch")
    message = workshop.generate()
    assert "Saved 1" in message and "Stopped" in message
    assert workshop.package.items[1].audio
    assert workshop.ledger["attempts"]["ru_pilot_03"]["status"] == "uncertain"
    with pytest.raises(ValueError, match="uncertain"):
        workshop.preflight("eleven_v3", VOICES, 20000, "batch")
    plan = workshop.preflight("eleven_v3", VOICES, 20000, "batch", acknowledge_uncertain=True)
    assert len(plan["scripts"]) == 10
    assert "Saved 10" in workshop.generate()
    assert len(workshop.client.calls) == 13


def test_restart_does_not_restore_key_and_marks_inflight_uncertain(workshop):
    workshop.ledger["attempts"]["ru_pilot_01"] = {"status": "inflight", "count": 1}
    workshop.save()
    resumed = Workshop(workshop.directory)
    assert resumed.client is None and resumed.catalog is None
    assert resumed.ledger["attempts"]["ru_pilot_01"]["status"] == "uncertain"
    with pytest.raises(ValueError, match="credentials"):
        resumed.preflight("eleven_v3", VOICES, 20000)


def test_export_and_session_isolation(workshop, tmp_path, caplog):
    other = Workshop(tmp_path / "other")
    pilot(workshop)
    assert other.client is None and other.package.items[0].audio is None
    with pytest.raises(ValueError):
        other.preview("ru_pilot_01")
    archive = workshop.export()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert any(n.startswith("audio/") for n in z.namelist())
        assert all(KEY.encode() not in z.read(n) for n in z.namelist())
        assert {x["review"]["status"] for x in json.loads(z.read("package.json"))["items"]} == {"draft"}
    assert KEY not in caplog.text
    assert "data:audio/mpeg;base64" in workshop.preview("ru_pilot_01")
    assert str(workshop.directory) not in workshop.preview("ru_pilot_01")
    assert KEY not in "".join(p.read_text(encoding="utf-8") for p in workshop.directory.glob("*.json"))


def test_private_import_cannot_approve_or_read_external_audio(workshop):
    pilot(workshop)
    data = workshop.package.model_dump(mode="json")
    data["items"][0]["review"] = {"status": "approved", "reviewer": "Pretend admin", "reviewed_at": "today", "reuse_attested": True}
    data["items"][0]["audio"]["path"] = "../secret.mp3"
    workshop.edit(json.dumps(data))
    assert workshop.package.items[0].review.status == "draft"
    assert workshop.package.items[0].audio is None
    assert workshop.ledger["pilot_approval"] is None
    assert all(x.review.status == "draft" for x in read_package(MANIFEST).items)


def test_regeneration_limit_and_double_click_lock(workshop):
    pilot(workshop)
    for _ in range(2):
        workshop.preflight("eleven_v3", VOICES, 20000, "selected", "ru_pilot_01")
        workshop.generate()
    with pytest.raises(ValueError, match="three"):
        workshop.preflight("eleven_v3", VOICES, 20000, "selected", "ru_pilot_01")
    workshop.lock.acquire()
    try:
        with pytest.raises(ValueError, match="progress"):
            workshop.generate()
    finally:
        workshop.lock.release()


@pytest.mark.parametrize("status,uncertain", [(401, False), (403, False), (402, False), (422, False), (429, False), (500, True)])
def test_provider_errors_sanitized_without_retry(status, uncertain):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=KEY)
    client = ElevenLabs(KEY, httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error:
        client.dialogue(read_package(PILOTS).items[0].turns, VOICES, "eleven_v3")
    assert error.value.uncertain == uncertain
    assert KEY not in str(error.value) and len(calls) == 1


def test_catalog_keeps_multilingual_defaults_and_prioritizes_russian():
    pages = []
    def handler(request):
        if request.url.path == "/v1/user/subscription":
            return httpx.Response(200, json={"tier": "free"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json=[{"model_id": "eleven_v3", "can_do_text_to_speech": True}])
        assert request.url.path == "/v2/voices"
        assert "language" not in request.url.params
        pages.append(request.url.params.get("next_page_token"))
        if len(pages) == 1:
            return httpx.Response(200, json={"voices": [
                {"voice_id": "default", "name": "Default", "category": "premade", "labels": {"language": "en"}},
                {"voice_id": "clone", "name": "Clone", "category": "cloned"}], "next_page_token": "page2"})
        return httpx.Response(200, json={"voices": [
            {"voice_id": "russian", "name": "Russian", "category": "generated", "labels": {"language": "ru"}}]})
    catalog = ElevenLabs(KEY, httpx.MockTransport(handler)).catalog()
    assert pages == [None, "page2"]
    assert [v["voice_id"] for v in catalog["voices"]] == ["russian", "default"]


def test_official_dialogue_payload_and_timeout():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/v1/text-to-dialogue"
        assert request.headers["xi-api-key"] == KEY
        body = json.loads(request.content)
        assert body["model_id"] == "eleven_v3" and body["language_code"] == "ru"
        assert body["inputs"][0]["voice_id"] == VOICES["A"]
        assert body["inputs"][1]["voice_id"] == VOICES["B"]
        raise httpx.ReadTimeout("untrusted text " + KEY)
    client = ElevenLabs(KEY, httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error:
        client.dialogue(read_package(PILOTS).items[0].turns, VOICES, "eleven_v3")
    assert error.value.uncertain and len(calls) == 1 and KEY not in str(error.value)


@pytest.mark.parametrize("mode", ["Adaptive Assessment", "Adaptive Diagnostic", "Full CA Simulation"])
def test_all_assessment_modes_use_local_presets_never_providers(monkeypatch, approved_bank, tmp_path, mode):
    from ui import callbacks as cb
    from core.storage import LocalStorage
    monkeypatch.setattr(cb, "PRESET_BANK", approved_bank)
    monkeypatch.setattr(cb, "STORAGE", LocalStorage(tmp_path / "sessions", tmp_path / "history"))
    monkeypatch.setattr(cb, "EXPORT_DIR", tmp_path / "exports")
    def prohibited(*args, **kwargs):
        pytest.fail("An assessment called a generation or remote-bank service")
    monkeypatch.setattr(cb.GENERATOR, "generate_and_store", prohibited)
    monkeypatch.setattr(cb.BANK_PERSISTENCE, "ensure_audio_available", prohibited)
    monkeypatch.setattr(cb.BANK_PERSISTENCE, "prefetch_audio", prohibited)
    monkeypatch.setattr(cb, "generate_dialogue_cached_tts", prohibited)
    monkeypatch.setattr(cb, "_prefetch_selected_playback", prohibited)
    lengths = {"Adaptive Assessment": "Complete passages", "Adaptive Diagnostic": "Efficient — 18 questions per skill",
               "Full CA Simulation": "Shortened practice — 12 questions per skill / 30 minutes"}
    if mode == "Adaptive Diagnostic":
        from core.constants import DIAGNOSTIC_LENGTHS
        lengths[mode] = next(iter(DIAGNOSTIC_LENGTHS))
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    result = cb.start_session_callback(mode, "Listening", "1+", "2", lengths[mode], "Off", [], [],
                                       "After each passage", False, True, "Starter", "Normal", "", "Fresh AI preferred")
    state, bundle = result[:2]
    assert state and bundle and state.content_source == "bank_only"
    playback = cb.play_audio_callback(state, bundle)
    assert "<audio" in playback[1]["value"]
    # Only Gradio server-side State contains transcript/keys; rendered controls do not.
    visible = json.dumps(result[3:], default=str)
    assert bundle["passage"]["passage_ru"] not in visible
    assert bundle["questions"][0]["rationale_en"] not in visible


def test_web_has_no_shared_curator_callback():
    from app import demo, launch_kwargs
    names = [getattr(fn.fn, "__name__", "") for fn in demo.fns.values()]
    assert "promote" not in names
    assert all("workshop" not in path.lower() for path in launch_kwargs()["allowed_paths"])
    from ui.workshop import build_workshop
    assert "curate_assessment" not in build_workshop.__code__.co_names


def test_named_curator_can_approve_fixture_without_touching_production(tmp_path):
    from scripts.curate_assessment import promote
    item = next(x for x in read_package(MANIFEST).items if x.passage.skill == "reading")
    package_path = tmp_path / "draft.json"
    manifest = tmp_path / "shared.json"
    write_package(package_path, ContentPackage(items=[item]))
    with pytest.raises(ValueError, match="attestation"):
        promote(package_path, item.id, "TEST reviewer", "TEST-only review", False, manifest, tmp_path)
    promote(package_path, item.id, "TEST reviewer", "TEST-only review", True, manifest, tmp_path)
    shared = PresetBank(manifest, tmp_path).load()
    assert len(shared.active_passages("reading", item.passage.language)) == 1
    with pytest.raises(ValueError, match="higher"):
        promote(package_path, item.id, "TEST reviewer", "TEST-only review", True, manifest, tmp_path)
    assert all(x.review.status == "draft" for x in read_package(MANIFEST).items)


def test_session_secret_and_secret_metadata_rejected(workshop):
    raw = workshop.package.model_dump_json()
    with pytest.raises(ValueError, match="credential"):
        workshop.edit(raw.replace("Dinner", KEY))
    data = json.loads(raw)
    data["items"][0]["passage"]["voice_metadata"] = {"api_key": "not-allowed"}
    with pytest.raises(ValueError):
        workshop.edit(json.dumps(data))
    assert "api_key" not in (workshop.directory / "package.json").read_text(encoding="utf-8")


def test_private_cleanup_removes_files_and_credentials(tmp_path, monkeypatch):
    import core.content_workshop as module
    monkeypatch.setattr(module, "PRIVATE_ROOT", tmp_path)
    work = Workshop()
    work.configure(KEY, FakeProvider)
    path = work.directory
    assert path.exists()
    work.close()
    assert not path.exists() and work.client is None and work._secrets == []


def test_text_authoring_uses_only_supplied_key(monkeypatch):
    from core import dialogue_authoring as module
    from core import generation
    monkeypatch.setenv("GROQ_API_KEY", "owner-key-must-not-be-used")
    monkeypatch.setenv("GEMINI_API_KEY", "owner-gemini-must-not-be-used")
    item = read_package(PILOTS).items[0]
    class Provider:
        def __init__(self, settings, purpose):
            assert settings.groq_api_key == KEY
            assert settings.gemini_api_key is None and settings.hf_token is None
            assert settings.provider_max_retries == 0 and settings.max_provider_attempts_per_stage == 1
        def generate_json(self, system, prompt, schema, **kwargs):
            return schema(topic="Dinner", orientation_en="Two people discuss dinner.", speakers=item.speakers,
                          turns=item.turns, questions=[{k: getattr(q, k) for k in module.DraftQuestion.model_fields} for q in item.questions])
    monkeypatch.setattr(generation, "HostedProvider", Provider)
    result = module.author(KEY, "fixture-model", "Dinner")
    assert result.review.status == "draft" and KEY not in result.model_dump_json()


def test_audition_is_budgeted_and_cannot_unlock_batch(workshop):
    plan = workshop.preflight("eleven_v3", VOICES, 20000, "audition")
    assert plan["characters_this_run"] > 0
    workshop.generate()
    assert workshop.ledger["spent_characters"] == plan["characters_this_run"]
    assert "data:audio" in workshop.preview("voice_audition")
    with pytest.raises(ValueError, match="pilot"):
        workshop.approve_voices()
    with pytest.raises(ValueError, match="pilot"):
        workshop.preflight("eleven_v3", VOICES, 20000, "batch")


@pytest.mark.parametrize("mode", ["Adaptive Assessment", "Adaptive Diagnostic", "Full CA Simulation"])
@pytest.mark.parametrize("skill", ["Reading", "Listening", "Reading + Listening (separate sections)"])
def test_empty_preset_bank_does_not_start_or_export_a_test(monkeypatch, approved_bank, tmp_path, mode, skill):
    from ui import callbacks as cb
    from core.constants import DIAGNOSTIC_LENGTHS
    from core.storage import LocalStorage
    monkeypatch.setattr(cb, "PRESET_BANK", approved_bank)
    monkeypatch.setattr(cb, "STORAGE", LocalStorage(tmp_path / "sessions", tmp_path / "history"))
    monkeypatch.setattr(cb, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(approved_bank, "active_passages", lambda *a: [])
    def unexpected_write(*args, **kwargs):
        pytest.fail("An unavailable assessment must not create a checkpoint or export")
    monkeypatch.setattr(cb.STORAGE, "save_checkpoint", unexpected_write)
    monkeypatch.setattr(cb, "build_exports", unexpected_write)
    length = ("Complete passages" if mode == "Adaptive Assessment" else next(iter(DIAGNOSTIC_LENGTHS))
              if mode == "Adaptive Diagnostic" else "Shortened practice — 12 questions per skill / 30 minutes")
    result = cb.start_session_callback(mode, skill, "1+", "2", length,
                                       "Off", [], [], "End of session", False, True, "Starter", "Normal", "")
    assert result[0] is None and result[1] is None
    assert "Assessment unavailable" in result[3]["value"]
    assert "Training Mode" in result[3]["value"]
    assert not result[27]["visible"] and result[27]["value"] == ""
    assert not result[28]["visible"] and not result[29]["visible"]
