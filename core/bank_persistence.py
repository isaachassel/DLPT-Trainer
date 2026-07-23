from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download

from .config import Settings
from .storage import atomic_write_text


@dataclass(frozen=True)
class BankPersistenceResult:
    local_path: str
    checksum: str
    record_count: int
    passage_count: int
    question_count: int
    audio_count: int
    validation_count: int
    remote_synced: bool
    note: str


class GeneratedBankPersistence:
    """Durability and health metadata for the generated-item overlay.

    The local/mounted JSONL file is always the immediate source of truth. When an
    HF Dataset repository is configured, the local bank is merged from the remote
    copy at startup and uploaded after every accepted bundle. Remote failure never
    removes an already accepted local item from the active in-memory bank.
    """

    def __init__(self, settings: Settings, project_root: str | Path):
        self.settings = settings
        self.project_root = Path(project_root)
        self.bank_path = settings.generated_bank_runtime_path(self.project_root)
        self.manifest_path = settings.generated_bank_manifest_runtime_path(self.project_root)
        self._lock = threading.RLock()
        self.last_note = ""
        self.last_remote_synced = False
        self.last_error: str | None = None

    @property
    def remote_enabled(self) -> bool:
        return bool(
            self.settings.hf_dataset_repo
            and self.settings.hf_token
            and self.settings.storage_backend in {"hf_dataset", "hybrid"}
        )

    @property
    def durable_locally(self) -> bool:
        return self.settings.persistent_storage_path is not None

    def _safe_error(self, exc: BaseException) -> str:
        text = str(exc)
        if self.settings.hf_token:
            text = text.replace(self.settings.hf_token, "[REDACTED]")
        return text[:400]

    @staticmethod
    def _record_key(record: dict[str, Any], fallback: str) -> tuple[str, str]:
        kind = str(record.get("kind", "unknown"))
        data = record.get("data") or {}
        identifier = str(data.get("id") or data.get("passage_id") or fallback)
        return kind, identifier

    @classmethod
    def _read_valid_records(cls, path: Path) -> tuple[list[dict[str, Any]], list[str]]:
        if not path.exists():
            return [], []
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
                if not isinstance(record, dict) or "kind" not in record or "data" not in record:
                    raise ValueError("record must contain kind and data")
                records.append(record)
            except Exception as exc:
                warnings.append(f"line {line_number}: {type(exc).__name__}")
        return records, warnings

    @classmethod
    def _merge_records(cls, remote_path: Path, local_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
        remote, remote_warnings = cls._read_valid_records(remote_path)
        local, local_warnings = cls._read_valid_records(local_path)
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        # Remote first, then local. Local records win because they may be newer
        # than the last successful remote synchronization.
        for source_name, records in (("remote", remote), ("local", local)):
            for index, record in enumerate(records):
                key = cls._record_key(record, f"{source_name}-{index}")
                if key not in merged:
                    order.append(key)
                merged[key] = record
        warnings = [f"remote {item}" for item in remote_warnings] + [f"local {item}" for item in local_warnings]
        return [merged[key] for key in order], warnings


    def _restore_remote_audio(self, records: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        cache_dir = self.settings.audio_cache_runtime_path(self.project_root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for record in records:
            if record.get("kind") != "audio":
                continue
            data = record.get("data") or {}
            source_name = Path(str(data.get("path") or "")).name or f"{data.get('id', 'audio')}.mp3"
            target = cache_dir / source_name
            try:
                downloaded = Path(
                    hf_hub_download(
                        repo_id=self.settings.hf_dataset_repo or "",
                        filename=f"audio/{source_name}",
                        repo_type="dataset",
                        token=self.settings.hf_token,
                        cache_dir=str(self.settings.runtime_path(Path("storage/cache/hf"), self.project_root, "cache/hf")),
                    )
                )
                fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(target.parent))
                os.close(fd)
                shutil.copyfile(downloaded, tmp_name)
                os.replace(tmp_name, target)
                data["path"] = str(target)
                record["data"] = data
            except Exception as exc:
                warnings.append(f"audio {data.get('id', source_name)}: {type(exc).__name__}")
        return warnings

    def bootstrap(self) -> str:
        """Merge the remote generated bank before ItemBank loads."""
        self.bank_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings.sync_generated_bank_on_startup or not self.remote_enabled:
            result = self.refresh_manifest(remote_synced=False)
            if self.remote_enabled:
                self.last_note = "Remote generated-bank synchronization is configured but startup pull is disabled."
            elif self.durable_locally:
                self.last_note = "Generated bank uses mounted persistent storage."
            else:
                self.last_note = (
                    "Generated bank uses local Space storage. Accepted items are immediately reusable, "
                    "but configure PERSISTENT_STORAGE_PATH or HF_DATASET_REPO for restart durability."
                )
            return self.last_note
        try:
            remote_file = Path(
                hf_hub_download(
                    repo_id=self.settings.hf_dataset_repo or "",
                    filename=self.settings.hf_dataset_bank_filename,
                    repo_type="dataset",
                    token=self.settings.hf_token,
                    cache_dir=str(self.settings.runtime_path(Path("storage/cache/hf"), self.project_root, "cache/hf")),
                )
            )
            records, warnings = self._merge_records(remote_file, self.bank_path)
            warnings.extend(self._restore_remote_audio(records))
            text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
            atomic_write_text(self.bank_path, text)
            result = self.refresh_manifest(remote_synced=True)
            warning_note = f" Ignored malformed records: {', '.join(warnings[:4])}." if warnings else ""
            self.last_note = (
                f"Generated bank merged from HF Dataset `{self.settings.hf_dataset_repo}`: "
                f"{result.passage_count} passages / {result.question_count} questions.{warning_note}"
            )
            self.last_remote_synced = True
            self.last_error = None
        except Exception as exc:
            self.last_remote_synced = False
            self.last_error = self._safe_error(exc)
            self.refresh_manifest(remote_synced=False)
            self.last_note = (
                "Remote generated-bank pull was unavailable; the validated local bank remains active. "
                f"Reason: {type(exc).__name__}."
            )
        return self.last_note

    def _upload_snapshot(self) -> None:
        api = HfApi(token=self.settings.hf_token)
        api.create_repo(
            repo_id=self.settings.hf_dataset_repo or "",
            repo_type="dataset",
            private=self.settings.hf_dataset_private,
            exist_ok=True,
            token=self.settings.hf_token,
        )
        api.upload_file(
            path_or_fileobj=self.bank_path,
            path_in_repo=self.settings.hf_dataset_bank_filename,
            repo_id=self.settings.hf_dataset_repo or "",
            repo_type="dataset",
            token=self.settings.hf_token,
            commit_message="Update validated Russian practice generated-item bank",
        )
        records, _ = self._read_valid_records(self.bank_path)
        for record in records:
            if record.get("kind") != "audio":
                continue
            data = record.get("data") or {}
            audio_path = Path(str(data.get("path") or ""))
            if not audio_path.exists() or audio_path.stat().st_size <= 0:
                continue
            api.upload_file(
                path_or_fileobj=audio_path,
                path_in_repo=f"audio/{audio_path.name}",
                repo_id=self.settings.hf_dataset_repo or "",
                repo_type="dataset",
                token=self.settings.hf_token,
                commit_message=f"Store generated listening audio {audio_path.name}",
            )

    def _upload_manifest(self) -> None:
        if not self.manifest_path.exists():
            return
        api = HfApi(token=self.settings.hf_token)
        api.upload_file(
            path_or_fileobj=self.manifest_path,
            path_in_repo=self.settings.hf_dataset_manifest_filename,
            repo_id=self.settings.hf_dataset_repo or "",
            repo_type="dataset",
            token=self.settings.hf_token,
            commit_message="Update generated-item bank manifest",
        )

    def after_local_commit(self, _: Path | None = None) -> BankPersistenceResult:
        """Refresh health metadata and, when configured, durably upload the bank."""
        with self._lock:
            result = self.refresh_manifest(remote_synced=False)
            if not self.settings.sync_generated_bank_on_write or not self.remote_enabled:
                if self.durable_locally:
                    note = (
                        f"Committed atomically to mounted storage and indexed immediately "
                        f"({result.passage_count} generated passages / {result.question_count} questions)."
                    )
                elif self.remote_enabled:
                    note = "Committed locally; automatic remote upload is disabled by configuration."
                else:
                    note = (
                        f"Committed atomically to the live Space bank and indexed immediately "
                        f"({result.passage_count} generated passages / {result.question_count} questions). "
                        "Local Space storage may reset after restart."
                    )
                self.last_note = note
                return BankPersistenceResult(**{**result.__dict__, "note": note})
            try:
                self._upload_snapshot()
                result = self.refresh_manifest(remote_synced=True)
                self._upload_manifest()
                note = (
                    f"Committed locally, indexed immediately, and synchronized to HF Dataset "
                    f"`{self.settings.hf_dataset_repo}` ({result.passage_count} generated passages / "
                    f"{result.question_count} questions)."
                )
                self.last_remote_synced = True
                self.last_error = None
            except Exception as exc:
                self.last_remote_synced = False
                self.last_error = self._safe_error(exc)
                note = (
                    "Committed locally and indexed immediately, but remote bank synchronization failed. "
                    f"The item remains usable in this runtime; reason: {type(exc).__name__}."
                )
            self.last_note = note
            return BankPersistenceResult(**{**result.__dict__, "remote_synced": self.last_remote_synced, "note": note})

    def refresh_manifest(self, *, remote_synced: bool) -> BankPersistenceResult:
        records, warnings = self._read_valid_records(self.bank_path)
        counts = {"passage": 0, "question": 0, "audio": 0, "validation": 0}
        for record in records:
            kind = str(record.get("kind", ""))
            if kind in counts:
                counts[kind] += 1
        raw = self.bank_path.read_bytes() if self.bank_path.exists() else b""
        checksum = hashlib.sha256(raw).hexdigest()
        manifest = {
            "schema_version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "bank_path": str(self.bank_path),
            "sha256": checksum,
            "record_count": len(records),
            "passage_count": counts["passage"],
            "question_count": counts["question"],
            "audio_count": counts["audio"],
            "validation_count": counts["validation"],
            "malformed_record_warnings": warnings,
            "storage_backend": self.settings.storage_backend,
            "persistent_volume": self.durable_locally,
            "hf_dataset_repo": self.settings.hf_dataset_repo,
            "remote_synced": remote_synced,
        }
        atomic_write_text(self.manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
        return BankPersistenceResult(
            local_path=str(self.bank_path),
            checksum=checksum,
            record_count=len(records),
            passage_count=counts["passage"],
            question_count=counts["question"],
            audio_count=counts["audio"],
            validation_count=counts["validation"],
            remote_synced=remote_synced,
            note="",
        )

    def status_text(self) -> str:
        result = self.refresh_manifest(remote_synced=self.last_remote_synced)
        if self.remote_enabled:
            durability = f"HF Dataset sync: `{self.settings.hf_dataset_repo}`"
        elif self.durable_locally:
            durability = "mounted persistent storage"
        else:
            durability = "ephemeral local Space storage"
        return (
            f"Generated bank: **{result.passage_count} passages / {result.question_count} questions** · "
            f"{durability} · checksum `{result.checksum[:10]}`"
        )
