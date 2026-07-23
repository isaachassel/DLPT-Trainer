from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .models import SessionCheckpoint, SessionState, UserHistory, utc_now


class StorageError(RuntimeError):
    pass


def safe_filename(value: str, fallback: str = "export") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("._")[:80]
    return cleaned or fallback


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class StorageBackend(Protocol):
    def save_checkpoint(self, state: SessionState) -> Path: ...
    def load_checkpoint(self, session_id: str) -> SessionState: ...
    def save_history(self, history: UserHistory) -> Path: ...
    def load_history(self, profile_id: str) -> UserHistory: ...


class LocalStorage:
    def __init__(self, session_dir: str | Path, history_dir: str | Path):
        self.session_dir = Path(session_dir)
        self.history_dir = Path(history_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, session_id: str) -> Path:
        return self.session_dir / f"{safe_filename(session_id, 'session')}.json"

    def _history_path(self, profile_id: str) -> Path:
        return self.history_dir / f"{safe_filename(profile_id, 'profile')}.json"

    @staticmethod
    def _checksum(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def save_checkpoint(self, state: SessionState) -> Path:
        payload = state.model_dump(mode="json")
        checkpoint = SessionCheckpoint(
            session_id=state.session_id,
            checksum=self._checksum(payload),
            session_payload=payload,
        )
        path = self._checkpoint_path(state.session_id)
        atomic_write_text(path, checkpoint.model_dump_json(indent=2))
        state.checkpoint_path = str(path)
        return path

    def load_checkpoint(self, session_id: str) -> SessionState:
        path = self._checkpoint_path(session_id)
        if not path.exists():
            raise StorageError(f"No checkpoint found for session code '{session_id}'.")
        try:
            checkpoint = SessionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StorageError("The checkpoint is corrupted or incompatible and was not loaded.") from exc
        if checkpoint.checksum != self._checksum(checkpoint.session_payload):
            raise StorageError("The checkpoint checksum does not match; recovery stopped safely.")
        try:
            return SessionState.model_validate(checkpoint.session_payload)
        except Exception as exc:
            raise StorageError("The checkpoint data is invalid and was not loaded.") from exc

    def save_history(self, history: UserHistory) -> Path:
        history.updated_at = utc_now()
        path = self._history_path(history.profile_id)
        atomic_write_text(path, history.model_dump_json(indent=2))
        return path

    def load_history(self, profile_id: str) -> UserHistory:
        if not profile_id.strip():
            return UserHistory(profile_id="anonymous")
        path = self._history_path(profile_id)
        if not path.exists():
            return UserHistory(profile_id=profile_id)
        try:
            return UserHistory.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StorageError("Saved user history is corrupted and was ignored safely.") from exc


def export_session_json(state: SessionState, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"session_{safe_filename(state.session_id)}.json"
    atomic_write_text(path, state.model_dump_json(indent=2))
    return path


def export_responses_csv(state: SessionState, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"responses_{safe_filename(state.session_id)}.csv"
    rows = [record.model_dump(mode="json") for record in state.responses]
    fieldnames = list(rows[0].keys()) if rows else [
        "session_id", "passage_id", "question_id", "skill", "mode", "selected_key", "correct_key", "is_correct"
    ]
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path
