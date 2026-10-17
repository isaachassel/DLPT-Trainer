"""Versioned, curator-reviewed content. No provider or writable practice overlay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .item_bank import ItemBank
from .models import AudioAsset, PassageItem, QuestionItem, StrictModel
from .storage import atomic_write_text
from .validation import content_hash, validate_passage, validate_question

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/assessment/bank.json"


def reject_secret_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            name = key.lower().replace("-", "_")
            if "api_key" in name or name in {"password", "secret", "authorization", "access_token", "hf_token", "xi_api_key"}:
                raise ValueError("Credentials are forbidden in content metadata")
            reject_secret_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_secret_fields(item)


class Review(StrictModel):
    status: Literal["draft", "approved", "rejected"] = "draft"
    reviewer: str = ""
    reviewed_at: str = ""
    notes: str = "Pending pronunciation, naturalness, question and ILR review."
    reuse_attested: bool = False


class Turn(StrictModel):
    speaker: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2000)


class AudioLicenseReview(StrictModel):
    reviewed_at: str
    reviewer: str
    commercial_use: bool
    attribution_required: bool
    model_status: Literal["generally_available", "beta", "unknown"]
    model_general_availability_date: str = ""
    creation_time_account_tier: str
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: list[str]
    scope: str


class Recording(StrictModel):
    provider: str = ""
    model: str = ""
    voice_ids: dict[str, str] = Field(default_factory=dict)
    seed: int | None = None
    generated_at: str = ""
    account_tier: str = "unknown"
    usage_terms: str = "Curator must verify plan, model status, voice/input rights and distribution terms."
    license_review: AudioLicenseReview | None = None


class ContentItem(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    content_version: int = Field(default=1, ge=1)
    passage: PassageItem
    questions: list[QuestionItem]
    turns: list[Turn] = Field(default_factory=list, max_length=100)
    speakers: dict[str, str] = Field(default_factory=dict)
    audio: AudioAsset | None = None
    audio_sha256: str | None = None
    recording: Recording = Field(default_factory=Recording)
    review: Review = Field(default_factory=Review)

    @model_validator(mode="after")
    def relationships(self):
        p = self.passage
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)) or set(ids) != set(p.question_ids):
            raise ValueError("Question IDs must uniquely match the passage question_ids")
        if any(q.passage_id != p.id or q.target_ilr != p.target_ilr for q in self.questions):
            raise ValueError("Questions must match the passage and its intended level")
        if p.content_hash != content_hash(p.passage_ru):
            raise ValueError("Passage content hash is stale; update it after editing")
        if self.turns:
            if any(t.speaker not in self.speakers for t in self.turns):
                raise ValueError("Every turn needs a declared speaker")
            if p.passage_ru != "\n".join(f"{t.speaker}: {t.text}" for t in self.turns):
                raise ValueError("Transcript must match the speaker turns")
        if self.audio and (self.audio.id != p.audio_asset_id or self.audio.url):
            raise ValueError("Audio must match its passage and use a local path, never a provider URL")
        if self.review.status == "approved" and not (
            self.review.reviewer.strip() and self.review.reviewed_at and self.review.reuse_attested
        ):
            raise ValueError("Approval requires a named reviewer, date and reuse attestation")
        return self


class ContentPackage(StrictModel):
    schema_version: Literal[1] = 1
    items: list[ContentItem] = Field(default_factory=list, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def secret_fields(cls, data):
        reject_secret_fields(data)
        return data

    @model_validator(mode="after")
    def unique_ids(self):
        for ids in ([x.id for x in self.items], [x.passage.id for x in self.items],
                    [q.id for x in self.items for q in x.questions],
                    [x.audio.id for x in self.items if x.audio]):
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate item, passage, question or audio ID")
        return self


def local_asset(base: Path, name: str | None) -> Path:
    if not name or Path(name).is_absolute() or ":" in name or "\\" in name:
        raise ValueError("Audio needs a relative package path with forward slashes")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("Missing audio or path outside the content package; restore the local asset")
    return path


def validate_item(item: ContentItem, base: Path) -> None:
    reports = [validate_passage(item.passage, item.questions)]
    reports += [validate_question(q, item.passage) for q in item.questions]
    failures = [reason for report in reports for reason in report.failure_reasons]
    if failures:
        raise ValueError("; ".join(failures))
    if item.passage.skill == "listening":
        if not item.audio or not item.audio_sha256:
            raise ValueError("Listening item needs a fixed local recording and audio_sha256")
        path = local_asset(base, item.audio.path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.audio_sha256:
            raise ValueError("Audio checksum mismatch; restore the reviewed recording")
        if path.stat().st_size < 512 or item.audio.transcript_hash != item.passage.content_hash:
            raise ValueError("Audio is empty or belongs to a different transcript")


def read_package(path: Path) -> ContentPackage:
    return ContentPackage.model_validate_json(path.read_text(encoding="utf-8"))


def write_package(path: Path, package: ContentPackage) -> None:
    reject_secret_fields(package.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, package.model_dump_json(indent=2))


class PresetBank(ItemBank):
    """Read-only deployment snapshot. Invalid approved items fail closed with warnings."""
    def __init__(self, manifest: Path = MANIFEST, asset_root: Path = ROOT):
        super().__init__(manifest)
        self.asset_root = asset_root
        self.reviewed_items: dict[str, ContentItem] = {}
        self.pending_count = 0

    def load(self):
        if self._loaded:
            return self
        try:
            package = read_package(self.path)
        except (OSError, ValueError):
            self.load_warnings.append("Preset manifest is missing or invalid. Run the local curator validate command.")
            package = ContentPackage()
        for item in package.items:
            if item.review.status != "approved":
                self.pending_count += 1
                continue
            try:
                validate_item(item, self.asset_root)
            except ValueError as exc:
                self.load_warnings.append(f"{item.id}: {exc}")
                continue
            self.reviewed_items[item.passage.id] = item
            self.passages[item.passage.id] = item.passage.model_copy(update={"status": "active", "validation_status": "accepted"})
            self.passage_origin[item.passage.id] = "approved_preset"
            for q in item.questions:
                self.questions[q.id] = q.model_copy(update={"status": "active", "validation_status": "accepted"})
            if item.audio:
                self.audio_assets[item.audio.id] = item.audio.model_copy(update={
                    "path": str(local_asset(self.asset_root, item.audio.path)), "validated": True})
        self._reindex()
        self._loaded = True
        return self

    def active_passages(self, skill, language=None):
        # Recheck files: a removed/corrupted asset must never trigger a remote fallback.
        result = []
        for passage in super().active_passages(skill, language):
            try:
                validate_item(self.reviewed_items[passage.id], self.asset_root)
                result.append(passage)
            except ValueError:
                continue
        return result

    def get_audio(self, audio_id):
        asset = super().get_audio(audio_id)
        if asset:
            item = next(x for x in self.reviewed_items.values() if x.audio and x.audio.id == audio_id)
            validate_item(item, self.asset_root)
        return asset

    def append_validated_bundle(self, *args, **kwargs):
        raise PermissionError("Shared preset content is managed only by the local curator CLI")


class PracticeBank(ItemBank):
    """Approved bundled content plus the optional writable training overlay.

    Legacy JSONL starter banks are never loaded. Keep the historical
    ``starter_bank`` origin key for compatibility with saved training sessions.
    """

    def __init__(self, writable_path: Path, *, manifest: Path = MANIFEST,
                 asset_root: Path = ROOT, **kwargs):
        super().__init__([manifest, writable_path], writable_path=writable_path, **kwargs)
        self.manifest = manifest
        self.asset_root = asset_root
        self.approved_bank = None

    def load(self):
        with self._lock:
            if self._loaded:
                return self
            approved = PresetBank(self.manifest, self.asset_root).load()
            self.approved_bank = approved
            self.passages.update(approved.passages)
            self.questions.update(approved.questions)
            self.audio_assets.update(approved.audio_assets)
            self.passage_origin.update({pid: "starter_bank" for pid in approved.passages})
            self.load_warnings.extend(approved.load_warnings)
            self._load_path(self.writable_path, required=False)
            self._reindex()
            self._loaded = True
        return self

    def active_passages(self, skill, language=None):
        approved_ids = {p.id for p in self.approved_bank.active_passages(skill, language)}
        return [p for p in super().active_passages(skill, language)
                if self.origin_for(p.id) == "generated_bank" or p.id in approved_ids]

    def get_audio(self, audio_id):
        if audio_id in self.approved_bank.audio_assets:
            return self.approved_bank.get_audio(audio_id)
        return super().get_audio(audio_id)
