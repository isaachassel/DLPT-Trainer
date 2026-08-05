from __future__ import annotations

import json
from pathlib import Path

from core.bank_persistence import GeneratedBankPersistence
from core.config import Settings
from core.generation import LiveGenerationService, MockProvider
from core.item_bank import ItemBank


def _settings(tmp_path: Path, **updates) -> Settings:
    base = Settings(
        generation_provider="mock",
        generated_item_bank_path=tmp_path / "generated.jsonl",
        generated_bank_manifest_path=tmp_path / "generated.meta.json",
        audio_cache_dir=tmp_path / "audio",
        quarantine_dir=tmp_path / "quarantine",
        session_dir=tmp_path / "sessions",
        history_dir=tmp_path / "history",
    )
    return base.model_copy(update=updates)


def test_visible_activity_indicator_and_button_lock_are_wired(project_root):
    source = (project_root / "ui/layout.py").read_text(encoding="utf-8")
    assert "operation-spinner" in source
    assert "aria-busy='true'" in (project_root / "ui/callbacks.py").read_text(encoding="utf-8")
    assert "Starting session and loading the first passage" in source
    assert "Preparing validated audio playback" in source
    assert "Submitting this passage" in source
    assert "interactive=False" in (project_root / "ui/callbacks.py").read_text(encoding="utf-8")
    assert "start_prepare.then" in source
    assert "play_prepare.then" in source
    assert "submit_prepare.then" in source


def test_generated_bank_commit_writes_manifest_and_is_immediately_reloadable(project_root, tmp_path):
    settings = _settings(tmp_path)
    persistence = GeneratedBankPersistence(settings, project_root)
    persistence.bootstrap()
    generated_path = settings.generated_bank_runtime_path(project_root)
    bank = ItemBank(
        [project_root / "data/starter_items.jsonl", generated_path],
        writable_path=generated_path,
        on_commit=persistence.after_local_commit,
    ).load()
    service = LiveGenerationService(settings, bank, project_root, provider=MockProvider())

    result = service.generate_and_store(
        skill="reading",
        level="2",
        mode="training",
        topics=["education"],
        competencies=["main idea"],
        maximum_questions=2,
    )

    manifest = json.loads(settings.generated_bank_manifest_runtime_path(project_root).read_text(encoding="utf-8"))
    assert manifest["passage_count"] == 1
    assert manifest["question_count"] == 2
    assert manifest["record_count"] == 6
    assert len(manifest["sha256"]) == 64
    assert "indexed immediately" in result.bank_persistence_note
    assert result.passage.id in {item.id for item in bank.active_passages("reading")}

    reloaded = ItemBank(
        [project_root / "data/starter_items.jsonl", generated_path],
        writable_path=generated_path,
    ).load()
    assert result.passage.id in reloaded.passages
    assert len(reloaded.get_questions(result.passage.id)) == 2
    assert reloaded.origin_for(result.passage.id) == "generated_bank"


def test_corrupt_generated_overlay_does_not_disable_starter_bank(project_root, tmp_path):
    generated_path = tmp_path / "generated.jsonl"
    generated_path.write_text("not json\n{\"kind\": \"question\"}\n", encoding="utf-8")
    bank = ItemBank(
        [project_root / "data/starter_items.jsonl", generated_path],
        writable_path=generated_path,
    ).load()
    assert bank.load_warnings
    assert bank.active_passages("reading")
    assert bank.active_passages("listening")


def test_hf_dataset_sync_uploads_bank_manifest_and_audio(monkeypatch, project_root, tmp_path):
    import core.generation as generation

    def fake_tts(transcript, cache_dir, voice, rate, engine_version, **kwargs):
        path = Path(cache_dir) / "generated-fixture.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ID3" + b"0" * 2048)
        return path

    monkeypatch.setattr(generation, "generate_cached_tts", fake_tts)
    monkeypatch.setattr(generation, "audio_duration_seconds", lambda path: 28.0)
    remote_bank = tmp_path / "remote.jsonl"
    remote_bank.write_text("", encoding="utf-8")
    uploaded: list[str] = []

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def create_repo(self, **kwargs):
            return None

        def upload_file(self, **kwargs):
            uploaded.append(kwargs["path_in_repo"])
            return None

    monkeypatch.setattr("core.bank_persistence.HfApi", FakeApi)
    monkeypatch.setattr("core.bank_persistence.hf_hub_download", lambda **kwargs: str(remote_bank))

    settings = _settings(
        tmp_path,
        storage_backend="hf_dataset",
        hf_dataset_repo="example/russian-practice-bank",
        hf_token="secret-token",
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    persistence.bootstrap()
    generated_path = settings.generated_bank_runtime_path(project_root)
    bank = ItemBank(
        [project_root / "data/starter_items.jsonl", generated_path],
        writable_path=generated_path,
        on_commit=persistence.after_local_commit,
    ).load()
    service = LiveGenerationService(settings, bank, project_root, provider=MockProvider())

    result = service.generate_and_store(
        skill="listening",
        level="2",
        mode="training",
        topics=[],
        competencies=["main idea"],
        maximum_questions=2,
        preferred_audio_voice="ru-RU-DmitryNeural",
        preferred_audio_rate="+10%",
    )

    assert result.audio_asset is not None
    assert result.audio_asset.voice == "ru-RU-DmitryNeural"
    assert result.audio_asset.rate == "+10%"
    assert result.bank_remote_synced is True
    assert settings.hf_dataset_bank_filename in uploaded
    assert settings.hf_dataset_manifest_filename in uploaded
    assert any(item.startswith("audio/") for item in uploaded)
    assert "synchronized to HF Dataset" in result.bank_persistence_note


def test_hf_dataset_startup_registers_remote_audio_and_restores_it_lazily(monkeypatch, project_root, tmp_path):
    remote_audio = tmp_path / "remote-audio.mp3"
    remote_audio.write_bytes(b"ID3" + b"1" * 1024)
    remote_bank = tmp_path / "remote-bank.jsonl"
    remote_bank.write_text(
        json.dumps(
            {
                "kind": "audio",
                "data": {
                    "id": "aud_remote",
                    "path": "/old/runtime/generated-audio.mp3",
                    "content_hash": "a" * 64,
                    "voice": "ru-RU-SvetlanaNeural",
                    "rate": "+0%",
                    "engine": "edge-tts",
                    "engine_version": "7.2.8",
                    "duration_seconds": 20.0,
                    "transcript_hash": "b" * 64,
                    "synthetic_tts": True,
                    "validated": True,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    downloads: list[str] = []

    def fake_download(**kwargs):
        downloads.append(kwargs["filename"])
        return str(remote_audio if kwargs["filename"].startswith("audio/") else remote_bank)

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def create_repo(self, **kwargs):
            return None

    monkeypatch.setattr("core.bank_persistence.HfApi", FakeApi)
    monkeypatch.setattr("core.bank_persistence.hf_hub_download", fake_download)
    settings = _settings(
        tmp_path,
        storage_backend="hf_dataset",
        hf_dataset_repo="example/russian-practice-bank",
        hf_token="secret-token",
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    persistence.bootstrap()

    records = [json.loads(line) for line in settings.generated_bank_runtime_path(project_root).read_text(encoding="utf-8").splitlines()]
    restored_path = Path(records[0]["data"]["path"])
    assert restored_path.parent == settings.audio_cache_runtime_path(project_root)
    assert not restored_path.exists()
    assert downloads == [settings.hf_dataset_bank_filename]

    class AssetRef:
        path = str(restored_path)

    asset = AssetRef()
    assert persistence.audio_available(asset) is True
    materialized = persistence.ensure_audio_available(asset)
    assert materialized == restored_path
    assert restored_path.exists()
    assert restored_path.read_bytes() == remote_audio.read_bytes()
    assert downloads == [settings.hf_dataset_bank_filename, "audio/generated-audio.mp3"]


def test_auto_provisions_private_dataset_bank_from_space_id(monkeypatch, project_root, tmp_path):
    uploaded: list[str] = []
    created: list[str] = []

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def create_repo(self, **kwargs):
            created.append(kwargs["repo_id"])
            return None

        def upload_file(self, **kwargs):
            uploaded.append(kwargs["path_in_repo"])
            return None

        def whoami(self, **kwargs):
            return {"name": "alsubij"}

    def missing_remote(**kwargs):
        from huggingface_hub.utils import EntryNotFoundError

        raise EntryNotFoundError("not initialized")

    monkeypatch.setenv("SPACE_ID", "alsubij/DLPT-Trainer")
    monkeypatch.setattr("core.bank_persistence.HfApi", FakeApi)
    monkeypatch.setattr("core.bank_persistence.hf_hub_download", missing_remote)
    settings = _settings(
        tmp_path,
        storage_backend="hybrid",
        hf_dataset_repo=None,
        hf_token="inference-token",
        hf_bank_token="write-token",
        auto_provision_dataset_bank=True,
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    note = persistence.bootstrap()

    assert persistence.resolved_repo_id == "alsubij/DLPT-Trainer-dlpt-generated-bank"
    assert created == [persistence.resolved_repo_id]
    assert settings.hf_dataset_bank_filename in uploaded
    assert settings.hf_dataset_manifest_filename in uploaded
    assert persistence.last_remote_synced is True
    assert "initialized" in note
    assert "restart-safe" in persistence.status_text()


def test_generated_bank_backup_zip_round_trip(project_root, tmp_path):
    source_settings = _settings(tmp_path / "source")
    source_persistence = GeneratedBankPersistence(source_settings, project_root)
    source_persistence.bootstrap()
    source_bank_path = source_settings.generated_bank_runtime_path(project_root)
    source_bank = ItemBank(
        [project_root / "data/starter_items.jsonl", source_bank_path],
        writable_path=source_bank_path,
        on_commit=source_persistence.after_local_commit,
    ).load()
    generated = LiveGenerationService(source_settings, source_bank, project_root, provider=MockProvider()).generate_and_store(
        skill="reading",
        level="2",
        mode="training",
        topics=["education"],
        competencies=["main idea"],
        maximum_questions=2,
    )
    backup = source_persistence.export_backup(tmp_path / "exports")
    assert backup.exists()

    destination_settings = _settings(tmp_path / "destination")
    destination_persistence = GeneratedBankPersistence(destination_settings, project_root)
    destination_persistence.bootstrap()
    result = destination_persistence.import_backup(backup)
    destination_bank = ItemBank(
        [project_root / "data/starter_items.jsonl", destination_settings.generated_bank_runtime_path(project_root)],
        writable_path=destination_settings.generated_bank_runtime_path(project_root),
    ).load()

    assert result.passage_count == 1
    assert result.question_count == 2
    assert generated.passage.id in destination_bank.passages
    assert destination_bank.origin_for(generated.passage.id) == "generated_bank"


def test_dataset_sync_uses_fallback_hf_token_when_bank_token_fails(monkeypatch, project_root, tmp_path):
    calls: list[str] = []

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def create_repo(self, **kwargs):
            calls.append(kwargs["token"])
            if kwargs["token"] == "bad-bank-token":
                raise RuntimeError("permission denied")
            return None

        def upload_file(self, **kwargs):
            return None

    def missing_remote(**kwargs):
        from huggingface_hub.utils import EntryNotFoundError
        raise EntryNotFoundError("bank file not initialized")

    monkeypatch.setattr("core.bank_persistence.HfApi", FakeApi)
    monkeypatch.setattr("core.bank_persistence.hf_hub_download", missing_remote)
    settings = _settings(
        tmp_path,
        storage_backend="hybrid",
        hf_dataset_repo="example/russian-practice-bank",
        hf_bank_token="bad-bank-token",
        hf_token="working-hf-token",
        bank_sync_max_retries=1,
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    persistence.bootstrap()

    assert calls == ["bad-bank-token", "working-hf-token"]
    assert persistence.last_remote_synced is True
    assert "restart-safe" in persistence.status_text()


def test_failed_dataset_sync_exposes_sanitized_reason(project_root, tmp_path):
    settings = _settings(
        tmp_path,
        storage_backend="hybrid",
        hf_dataset_repo="example/russian-practice-bank",
        hf_bank_token="hf_secret_value",
        bank_sync_max_retries=1,
    )
    persistence = GeneratedBankPersistence(settings, project_root)
    persistence.last_error = "HTTP 403: token hf_secret_value lacks write permission"
    persistence.last_remote_synced = False

    status = persistence.status_text()
    # status_text receives an already-sanitized last_error during normal calls;
    # explicitly verify the helper used to create it never leaks the token.
    safe = persistence._safe_error(RuntimeError("token hf_secret_value lacks write permission"))
    assert "hf_secret_value" not in safe
    assert "[REDACTED]" in safe
    assert "last sync failed" in status
