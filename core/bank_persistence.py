from __future__ import annotations

import hashlib
import logging
import json
import os
import re
import shutil
import tempfile
import time
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, HfHubHTTPError, RepositoryNotFoundError

from .config import Settings
from .storage import atomic_write_text


LOGGER = logging.getLogger("dlpt.persistence")


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
    """Durability, backup, restore, and health metadata for generated items.

    The local JSONL overlay remains the immediate source of truth so accepted
    content is usable without waiting for the network. On Hugging Face Spaces,
    the persistence layer can automatically provision a private Dataset repo,
    mirror each accepted bundle, and restore the overlay at startup.
    """

    BACKUP_SCHEMA_VERSION = 1
    MAX_BACKUP_COMPRESSED_BYTES = 100 * 1024 * 1024
    MAX_BACKUP_FILES = 512
    MAX_BACKUP_UNCOMPRESSED_BYTES = 300 * 1024 * 1024
    MAX_BACKUP_MEMBER_BYTES = 100 * 1024 * 1024
    MAX_JSONL_BYTES = 100 * 1024 * 1024
    MAX_COMPRESSION_RATIO = 200.0

    def __init__(self, settings: Settings, project_root: str | Path):
        self.settings = settings
        self.project_root = Path(project_root)
        self.bank_path = settings.generated_bank_runtime_path(self.project_root)
        self.manifest_path = settings.generated_bank_manifest_runtime_path(self.project_root)
        self._lock = threading.RLock()
        self.last_note = ""
        self.last_remote_synced = False
        self.last_error: str | None = None
        self.resolved_repo_id: str | None = settings.hf_dataset_repo
        self._remote_repo_confirmed = False
        self._active_token: str | None = None

    @property
    def token_candidates(self) -> tuple[str, ...]:
        candidates: list[str] = []
        for token in (self._active_token, self.settings.hf_bank_token, self.settings.hf_token):
            if token and token not in candidates:
                candidates.append(token)
        return tuple(candidates)

    @property
    def bank_token(self) -> str | None:
        candidates = self.token_candidates
        return candidates[0] if candidates else None

    @property
    def remote_enabled(self) -> bool:
        return bool(
            self.resolved_repo_id
            and self.bank_token
            and self.settings.storage_backend in {"hf_dataset", "hybrid"}
        )

    @property
    def durable_locally(self) -> bool:
        return self.settings.persistent_storage_path is not None

    @property
    def durable(self) -> bool:
        return self.durable_locally or (self.remote_enabled and self.last_remote_synced)

    def _safe_error(self, exc: BaseException) -> str:
        text = str(exc)
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        request_id = None
        headers = getattr(response, "headers", None)
        if headers:
            request_id = headers.get("x-request-id") or headers.get("X-Request-Id")
        prefix = f"HTTP {status}: " if status else ""
        suffix = f" (request {request_id})" if request_id else ""
        for secret in (self.settings.hf_token, self.settings.hf_bank_token, self.settings.groq_api_key):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        compact = " ".join(text.split())
        return f"{prefix}{compact}{suffix}"[:700]

    def _remote_call(self, action: str, operation):
        """Run a Hub operation with bounded retries and token fallback."""

        errors: list[str] = []
        candidates = self.token_candidates
        if not candidates:
            raise RuntimeError("No HF_BANK_TOKEN or HF_TOKEN is configured for generated-bank persistence.")
        for token_index, token in enumerate(candidates, start=1):
            for attempt in range(1, self.settings.bank_sync_max_retries + 1):
                try:
                    result = operation(token)
                    self._active_token = token
                    if token_index > 1:
                        LOGGER.info("Generated-bank %s succeeded with fallback token candidate %s", action, token_index)
                    return result
                except EntryNotFoundError:
                    # The repository is reachable; only the requested file is absent.
                    raise
                except RepositoryNotFoundError as exc:
                    errors.append(f"token {token_index}: {self._safe_error(exc)}")
                    break
                except HfHubHTTPError as exc:
                    errors.append(f"token {token_index} attempt {attempt}: {self._safe_error(exc)}")
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in {401, 403, 404}:
                        break
                    if attempt < self.settings.bank_sync_max_retries:
                        time.sleep(min(2 ** (attempt - 1), 4))
                except Exception as exc:
                    errors.append(f"token {token_index} attempt {attempt}: {self._safe_error(exc)}")
                    if attempt < self.settings.bank_sync_max_retries:
                        time.sleep(min(2 ** (attempt - 1), 4))
        detail = " | ".join(errors[-4:])
        raise RuntimeError(f"HF Dataset {action} failed for all configured bank tokens. {detail}")

    @staticmethod
    def _safe_slug(value: str, *, fallback: str = "dlpt-trainer") -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
        return (cleaned or fallback)[:72]

    def _resolve_repo_id(self) -> str | None:
        if self.resolved_repo_id:
            return self.resolved_repo_id
        if not self.settings.auto_provision_dataset_bank or not self.bank_token:
            return None
        if self.settings.storage_backend not in {"hf_dataset", "hybrid"}:
            return None

        space_id = os.getenv("SPACE_ID", "").strip()
        space_host = os.getenv("SPACE_HOST", "").strip()
        owner: str | None = None
        app_name = self.settings.app_name
        if "/" in space_id:
            owner, app_name = space_id.split("/", 1)
        else:
            try:
                identity = self._remote_call("identity check", lambda token: HfApi(token=token).whoami(token=token))
                owner = str(identity.get("name") or identity.get("fullname") or "").strip() or None
                if space_host:
                    app_name = space_host.removesuffix(".hf.space")
            except Exception as exc:
                self.last_error = self._safe_error(exc)
                return None

        if not owner:
            return None
        suffix = self._safe_slug(self.settings.auto_dataset_repo_suffix, fallback="dlpt-generated-bank")
        base = self._safe_slug(app_name)
        self.resolved_repo_id = f"{owner}/{base}-{suffix}"
        return self.resolved_repo_id

    def _ensure_local_bank_file(self) -> None:
        self.bank_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.bank_path.exists():
            atomic_write_text(self.bank_path, "")

    def _ensure_remote_repo(self) -> None:
        if self._remote_repo_confirmed:
            return
        repo_id = self._resolve_repo_id()
        if not repo_id or not self.bank_token:
            raise RuntimeError("No Dataset repository or write-capable bank token is available.")
        self._remote_call(
            "repository create/access check",
            lambda token: HfApi(token=token).create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=self.settings.hf_dataset_private,
                exist_ok=True,
                token=token,
            ),
        )
        self._remote_repo_confirmed = True
        LOGGER.info("Generated-bank Dataset repository ready repo=%s", repo_id)

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
    def _merge_records(cls, first_path: Path, second_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
        first, first_warnings = cls._read_valid_records(first_path)
        second, second_warnings = cls._read_valid_records(second_path)
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        # Second source wins for duplicate stable IDs, while unique records from
        # both sources are retained. This supports remote+local and import+local.
        for source_name, records in (("first", first), ("second", second)):
            for index, record in enumerate(records):
                key = cls._record_key(record, f"{source_name}-{index}")
                if key not in merged:
                    order.append(key)
                merged[key] = record
        warnings = [f"first {item}" for item in first_warnings] + [f"second {item}" for item in second_warnings]
        return [merged[key] for key in order], warnings

    def _cache_dir(self) -> Path:
        return self.settings.runtime_path(Path("storage/cache/hf"), self.project_root, "cache/hf")

    def _download_remote(self, filename: str) -> Path:
        repo_id = self.resolved_repo_id or ""
        return Path(
            self._remote_call(
                f"download {filename}",
                lambda token: hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    repo_type="dataset",
                    token=token,
                    cache_dir=str(self._cache_dir()),
                    force_download=False,
                ),
            )
        )

    def _restore_remote_audio(self, records: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        cache_dir = self.settings.audio_cache_runtime_path(self.project_root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        repo_id = self.resolved_repo_id or ""
        for record in records:
            if record.get("kind") != "audio":
                continue
            data = record.get("data") or {}
            source_name = Path(str(data.get("path") or "")).name or f"{data.get('id', 'audio')}.mp3"
            target = cache_dir / source_name
            try:
                downloaded = self._download_remote(f"audio/{source_name}")
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
        """Restore/merge a durable generated bank before ItemBank loads."""
        self._ensure_local_bank_file()
        self._resolve_repo_id()

        if not self.settings.sync_generated_bank_on_startup or not self.remote_enabled:
            self.refresh_manifest(remote_synced=False)
            if self.remote_enabled:
                self.last_note = "Remote generated-bank synchronization is configured but startup restore is disabled."
            elif self.durable_locally:
                self.last_note = "Generated bank uses mounted persistent storage."
            else:
                reason = f" Last persistence error: {self.last_error}." if self.last_error else ""
                self.last_note = (
                    "Generated bank is using ephemeral Space storage and will reset on restart. "
                    "Add a write-capable HF_BANK_TOKEN (or HF_TOKEN) so the app can automatically create a private Dataset backup, "
                    "or configure PERSISTENT_STORAGE_PATH." + reason
                )
            return self.last_note

        try:
            # Validate access and create the configured/derived Dataset before
            # attempting to restore its bank file. This avoids ambiguous 404s
            # where a missing private repo and an unreadable repo look identical.
            self._ensure_remote_repo()
            try:
                remote_file = self._download_remote(self.settings.hf_dataset_bank_filename)
                self._remote_repo_confirmed = True
            except EntryNotFoundError:
                # First run: initialize the private Dataset with the current local
                # snapshot (which may be empty) so future restarts are durable.
                self.refresh_manifest(remote_synced=False)
                self._upload_snapshot()
                result = self.refresh_manifest(remote_synced=True)
                self._upload_manifest()
                self.last_remote_synced = True
                self.last_error = None
                self.last_note = (
                    f"Private HF Dataset bank initialized at `{self.resolved_repo_id}`: "
                    f"{result.passage_count} passages / {result.question_count} questions."
                )
                return self.last_note

            records, warnings = self._merge_records(remote_file, self.bank_path)
            warnings.extend(self._restore_remote_audio(records))
            text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
            atomic_write_text(self.bank_path, text)
            result = self.refresh_manifest(remote_synced=True)
            warning_note = f" Ignored malformed records: {', '.join(warnings[:4])}." if warnings else ""
            self.last_note = (
                f"Startup restore snapshot from private HF Dataset `{self.resolved_repo_id}`: "
                f"{result.passage_count} saved AI-generated passages / {result.question_count} questions at launch. "
                f"Current totals appear above and may be higher after later accepted Fresh-AI generations.{warning_note}"
            )
            self.last_remote_synced = True
            self.last_error = None
            LOGGER.info("Generated-bank restore synchronized repo=%s passages=%s questions=%s", self.resolved_repo_id, result.passage_count, result.question_count)
        except (RepositoryNotFoundError, PermissionError) as exc:
            self.last_remote_synced = False
            self.last_error = self._safe_error(exc)
            self.refresh_manifest(remote_synced=False)
            self.last_note = (
                "Automatic private Dataset persistence could not be enabled. The current bank is temporary. "
                "Use a write-capable HF_BANK_TOKEN or explicitly set HF_DATASET_REPO. "
                f"Reason: {type(exc).__name__}: {self.last_error}."
            )
            LOGGER.error("Generated-bank startup sync failed repo=%s error=%s", self.resolved_repo_id, self.last_error)
        except Exception as exc:
            self.last_remote_synced = False
            self.last_error = self._safe_error(exc)
            self.refresh_manifest(remote_synced=False)
            self.last_note = (
                "Remote generated-bank restore was unavailable; the validated local bank remains active for this runtime only. "
                f"Reason: {type(exc).__name__}: {self.last_error}."
            )
            LOGGER.error("Generated-bank startup sync failed repo=%s error=%s", self.resolved_repo_id, self.last_error)
        return self.last_note

    def _upload_snapshot(self) -> None:
        self._ensure_local_bank_file()
        self._ensure_remote_repo()
        repo_id = self.resolved_repo_id or ""
        self._remote_call(
            "upload generated bank",
            lambda token: HfApi(token=token).upload_file(
                path_or_fileobj=self.bank_path,
                path_in_repo=self.settings.hf_dataset_bank_filename,
                repo_id=repo_id,
                repo_type="dataset",
                token=token,
                commit_message="Update validated multilingual practice generated-item bank",
            ),
        )
        records, _ = self._read_valid_records(self.bank_path)
        # Fetch the remote file index once and upload only genuinely new audio.
        # The previous implementation attempted every historical MP3 after each
        # accepted item, producing dozens of empty-commit warnings and needless
        # network traffic.
        def _list_remote_files(token: str) -> list[str]:
            api = HfApi(token=token)
            list_files = getattr(api, "list_repo_files", None)
            if list_files is None:
                # Compatibility with older clients and lightweight test doubles.
                return []
            return list_files(repo_id=repo_id, repo_type="dataset", token=token)

        remote_files = set(
            self._remote_call("list generated-bank files", _list_remote_files)
        )
        uploaded_audio: set[str] = set()
        for record in records:
            if record.get("kind") != "audio":
                continue
            data = record.get("data") or {}
            audio_path = Path(str(data.get("path") or ""))
            remote_name = f"audio/{audio_path.name}"
            if (
                not audio_path.exists()
                or audio_path.stat().st_size <= 0
                or audio_path.name in uploaded_audio
                or remote_name in remote_files
            ):
                continue
            self._remote_call(
                f"upload audio {audio_path.name}",
                lambda token, path=audio_path: HfApi(token=token).upload_file(
                    path_or_fileobj=path,
                    path_in_repo=f"audio/{path.name}",
                    repo_id=repo_id,
                    repo_type="dataset",
                    token=token,
                    commit_message=f"Store generated listening audio {path.name}",
                ),
            )
            uploaded_audio.add(audio_path.name)
            remote_files.add(remote_name)

    def _upload_manifest(self) -> None:
        if not self.manifest_path.exists():
            return
        self._ensure_remote_repo()
        self._remote_call(
            "upload bank manifest",
            lambda token: HfApi(token=token).upload_file(
                path_or_fileobj=self.manifest_path,
                path_in_repo=self.settings.hf_dataset_manifest_filename,
                repo_id=self.resolved_repo_id or "",
                repo_type="dataset",
                token=token,
                commit_message="Update generated-item bank manifest",
            ),
        )

    def after_local_commit(self, _: Path | None = None) -> BankPersistenceResult:
        """Refresh metadata and durably mirror every accepted bundle."""
        with self._lock:
            self._resolve_repo_id()
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
                        f"({result.passage_count} generated passages / {result.question_count} questions), "
                        "but this copy will reset on restart. Export a backup or add a write-capable HF_BANK_TOKEN."
                    )
                self.last_note = note
                return BankPersistenceResult(**{**result.__dict__, "note": note})
            try:
                self._upload_snapshot()
                result = self.refresh_manifest(remote_synced=True)
                self._upload_manifest()
                note = (
                    f"Committed locally, indexed immediately, and synchronized to HF Dataset (private) "
                    f"`{self.resolved_repo_id}` ({result.passage_count} generated passages / "
                    f"{result.question_count} questions)."
                )
                self.last_remote_synced = True
                self.last_error = None
            except Exception as exc:
                self.last_remote_synced = False
                self.last_error = self._safe_error(exc)
                note = (
                    "Committed locally and indexed immediately, but durable synchronization failed. "
                    "The item is usable only until the next restart unless you export it. "
                    f"Reason: {type(exc).__name__}: {self.last_error}."
                )
                LOGGER.error("Generated-bank write sync failed repo=%s error=%s", self.resolved_repo_id, self.last_error)
            self.last_note = note
            return BankPersistenceResult(**{**result.__dict__, "remote_synced": self.last_remote_synced, "note": note})

    def sync_now(self) -> BankPersistenceResult:
        """Explicitly test access and push the current bank to durable storage."""

        with self._lock:
            self._resolve_repo_id()
            if not self.remote_enabled:
                raise RuntimeError(
                    "Dataset synchronization is not configured. Add HF_BANK_TOKEN and HF_DATASET_REPO, "
                    "or enable automatic Dataset provisioning."
                )
            try:
                self._ensure_remote_repo()
                self.refresh_manifest(remote_synced=False)
                self._upload_snapshot()
                result = self.refresh_manifest(remote_synced=True)
                self._upload_manifest()
                self.last_remote_synced = True
                self.last_error = None
                self.last_note = (
                    f"Manual synchronization succeeded for `{self.resolved_repo_id}`: "
                    f"{result.passage_count} passages / {result.question_count} questions."
                )
                LOGGER.info("Generated-bank manual sync succeeded repo=%s", self.resolved_repo_id)
                return BankPersistenceResult(**{**result.__dict__, "remote_synced": True, "note": self.last_note})
            except Exception as exc:
                self.last_remote_synced = False
                self.last_error = self._safe_error(exc)
                self.refresh_manifest(remote_synced=False)
                LOGGER.error("Generated-bank manual sync failed repo=%s error=%s", self.resolved_repo_id, self.last_error)
                raise RuntimeError(
                    "Generated-bank synchronization failed. Confirm HF_BANK_TOKEN has write access to the Dataset. "
                    f"Details: {self.last_error}"
                ) from exc

    def export_backup(self, destination_dir: str | Path) -> Path:
        """Create a portable ZIP containing generated JSONL, manifest, and audio."""
        with self._lock:
            self._ensure_local_bank_file()
            result = self.refresh_manifest(remote_synced=self.last_remote_synced)
            destination = Path(destination_dir)
            destination.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target = destination / f"generated-bank-backup-{stamp}-{result.checksum[:10]}.zip"
            records, _ = self._read_valid_records(self.bank_path)
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(self.bank_path, arcname="generated_items.jsonl")
                if self.manifest_path.exists():
                    archive.write(self.manifest_path, arcname="generated_items.meta.json")
                seen_audio: set[str] = set()
                for record in records:
                    if record.get("kind") != "audio":
                        continue
                    audio_path = Path(str((record.get("data") or {}).get("path") or ""))
                    if audio_path.exists() and audio_path.stat().st_size > 0 and audio_path.name not in seen_audio:
                        archive.write(audio_path, arcname=f"audio/{audio_path.name}")
                        seen_audio.add(audio_path.name)
                archive.writestr(
                    "backup_info.json",
                    json.dumps(
                        {
                            "schema_version": self.BACKUP_SCHEMA_VERSION,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "passage_count": result.passage_count,
                            "question_count": result.question_count,
                            "sha256": result.checksum,
                            "remote_repo": self.resolved_repo_id,
                        },
                        indent=2,
                    ),
                )
            return target

    @staticmethod
    def _safe_zip_member(name: str) -> bool:
        path = PurePosixPath(name)
        return not path.is_absolute() and ".." not in path.parts

    @classmethod
    def _validate_zip_limits(cls, source_path: Path, archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        if source_path.stat().st_size > cls.MAX_BACKUP_COMPRESSED_BYTES:
            raise ValueError("Backup ZIP exceeds the 100 MB compressed-size limit.")
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) > cls.MAX_BACKUP_FILES:
            raise ValueError(f"Backup ZIP contains more than {cls.MAX_BACKUP_FILES} files.")
        total_size = 0
        for member in members:
            if not cls._safe_zip_member(member.filename):
                raise ValueError("Backup contains an unsafe path.")
            if member.flag_bits & 0x1:
                raise ValueError("Encrypted backup members are not supported.")
            if member.file_size > cls.MAX_BACKUP_MEMBER_BYTES:
                raise ValueError(f"Backup member is too large: {member.filename}")
            total_size += member.file_size
            if total_size > cls.MAX_BACKUP_UNCOMPRESSED_BYTES:
                raise ValueError("Backup exceeds the 300 MB total uncompressed-size limit.")
            if member.file_size >= 1024 * 1024:
                ratio = member.file_size / max(1, member.compress_size)
                if ratio > cls.MAX_COMPRESSION_RATIO:
                    raise ValueError(f"Backup member has an unsafe compression ratio: {member.filename}")
        return members

    def import_backup(self, source: str | Path) -> BankPersistenceResult:
        """Merge a portable backup into the live generated overlay safely."""
        with self._lock:
            source_path = Path(source)
            if not source_path.exists():
                raise FileNotFoundError(source_path)
            self._ensure_local_bank_file()
            work_dir = Path(tempfile.mkdtemp(prefix="bank-import-"))
            try:
                incoming_path = work_dir / "incoming.jsonl"
                if source_path.suffix.lower() == ".jsonl":
                    if source_path.stat().st_size > self.MAX_JSONL_BYTES:
                        raise ValueError("Generated-bank JSONL exceeds the 100 MB import limit.")
                    shutil.copyfile(source_path, incoming_path)
                elif source_path.suffix.lower() == ".zip":
                    with zipfile.ZipFile(source_path, "r") as archive:
                        members = self._validate_zip_limits(source_path, archive)
                        names = [member.filename for member in members]
                        bank_name = next((name for name in names if PurePosixPath(name).name == "generated_items.jsonl"), None)
                        if not bank_name:
                            raise ValueError("Backup does not contain generated_items.jsonl.")
                        bank_info = archive.getinfo(bank_name)
                        if bank_info.file_size > self.MAX_JSONL_BYTES:
                            raise ValueError("Generated-bank JSONL exceeds the 100 MB import limit.")
                        incoming_path.write_bytes(archive.read(bank_name))
                        cache_dir = self.settings.audio_cache_runtime_path(self.project_root)
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        for name in names:
                            pure = PurePosixPath(name)
                            if len(pure.parts) == 2 and pure.parts[0] == "audio" and pure.suffix.lower() == ".mp3":
                                target = cache_dir / pure.name
                                fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(cache_dir))
                                os.close(fd)
                                Path(tmp_name).write_bytes(archive.read(name))
                                os.replace(tmp_name, target)
                else:
                    raise ValueError("Generated-bank imports must be .zip or .jsonl files.")

                incoming_records, warnings = self._read_valid_records(incoming_path)
                if warnings:
                    raise ValueError(f"Backup contains malformed records: {', '.join(warnings[:4])}")
                cache_dir = self.settings.audio_cache_runtime_path(self.project_root)
                for record in incoming_records:
                    if record.get("kind") == "audio":
                        data = record.get("data") or {}
                        name = Path(str(data.get("path") or "")).name
                        restored = cache_dir / name
                        if name and restored.exists():
                            data["path"] = str(restored)
                            record["data"] = data
                normalized_incoming = work_dir / "normalized.jsonl"
                atomic_write_text(
                    normalized_incoming,
                    "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in incoming_records),
                )
                # Schema, relationship, audio, and duplicate-ID checks run before
                # the import can touch the live overlay. This is deterministic
                # integrity validation, not a human-authenticity gate.
                from .item_bank import ItemBank

                validation_bank = ItemBank(
                    [
                        self.settings.starter_bank_runtime_path(self.project_root),
                        self.settings.mandarin_starter_bank_runtime_path(self.project_root),
                        normalized_incoming,
                    ],
                    writable_path=normalized_incoming,
                ).load()
                validation_errors = validation_bank.validate_operational_bank()
                if validation_bank.load_warnings:
                    validation_errors.extend(validation_bank.load_warnings)
                if validation_errors:
                    raise ValueError(
                        "Imported bank failed deterministic integrity checks: "
                        + "; ".join(validation_errors[:8])
                    )
                records, merge_warnings = self._merge_records(normalized_incoming, self.bank_path)
                if merge_warnings:
                    raise ValueError(f"Could not safely merge backup: {', '.join(merge_warnings[:4])}")
                atomic_write_text(
                    self.bank_path,
                    "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
                )
                return self.after_local_commit(self.bank_path)
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

    def refresh_manifest(self, *, remote_synced: bool) -> BankPersistenceResult:
        self._ensure_local_bank_file()
        records, warnings = self._read_valid_records(self.bank_path)
        counts = {"passage": 0, "question": 0, "audio": 0, "validation": 0}
        for record in records:
            kind = str(record.get("kind", ""))
            if kind in counts:
                counts[kind] += 1
        raw = self.bank_path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        manifest = {
            "schema_version": 2,
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
            "hf_dataset_repo": self.resolved_repo_id,
            "remote_synced": remote_synced,
            "restart_durable": self.durable_locally or (bool(self.resolved_repo_id) and remote_synced),
            "last_error": self.last_error,
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
        if self.remote_enabled and self.last_remote_synced:
            durability = f"restart-safe private HF Dataset: `{self.resolved_repo_id}`"
            icon = "✅"
        elif self.durable_locally:
            durability = "restart-safe mounted persistent storage"
            icon = "✅"
        elif self.remote_enabled:
            detail = f" · last error: {self.last_error[:240]}" if self.last_error else ""
            durability = f"private HF Dataset configured but last sync failed: `{self.resolved_repo_id}`{detail}"
            icon = "⚠️"
        else:
            durability = "NOT restart-safe — ephemeral local Space storage"
            icon = "⚠️"
        return (
            f"{icon} Saved AI-generated content: **{result.passage_count} passages / {result.question_count} questions** · "
            f"{durability} · checksum `{result.checksum[:10]}`"
        )
