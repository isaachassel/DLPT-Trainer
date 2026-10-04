"""Private authoring sessions with durable, conservative paid-request accounting."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import tempfile
import threading
import time
import zipfile
from pydantic import SecretStr
from datetime import datetime, timezone
from pathlib import Path

from .elevenlabs import ElevenLabs, ProviderError
from .models import AudioAsset
from .preset_bank import ContentPackage, Recording, Review, ROOT, local_asset, read_package, write_package
from .storage import atomic_write_text

PILOTS = ROOT / "data/pilots/russian_0plus_dialogues.json"
PRIVATE_ROOT = Path(tempfile.gettempdir()) / "dlpt-private-workshops"


def now():
    return datetime.now(timezone.utc).isoformat()


def cleanup_old_workspaces(max_age=86400):
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    for child in PRIVATE_ROOT.iterdir():
        if child.is_dir() and not child.is_symlink() and child.name.startswith("session-"):
            stamp = child / "ledger.json"
            if stamp.exists() and time.time() - stamp.stat().st_mtime > max_age:
                shutil.rmtree(child)


class Workshop:
    """Only held by server-side gr.State; never sent as a browser component value."""
    def __init__(self, directory: Path | None = None):
        PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
        self.directory = directory or Path(tempfile.mkdtemp(prefix="session-", dir=PRIVATE_ROOT))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client = None
        self.catalog = None
        self.lock = threading.Lock()
        self.plan = None
        self._secrets = []
        self.ledger = {"spent_characters": 0, "attempts": {}, "pilot_approval": None}
        if (self.directory / "package.json").exists():
            self.package = read_package(self.directory / "package.json")
            self.ledger = json.loads((self.directory / "ledger.json").read_text(encoding="utf-8"))
            for entry in self.ledger["attempts"].values():
                if entry["status"] == "inflight":
                    entry["status"] = "uncertain"
        else:
            self.package = read_package(PILOTS)
        self.save()

    def __deepcopy__(self, memo):
        # Gradio state is created lazily, never as a shared initial value.
        raise TypeError("Workshop must be created per session, not copied")

    def save(self):
        self._check_secret_text(self.package.model_dump_json() + json.dumps(self.ledger))
        write_package(self.directory / "package.json", self.package)
        atomic_write_text(self.directory / "ledger.json", json.dumps(self.ledger, indent=2))

    def close(self):
        with self.lock:
            self.client = self.catalog = self.plan = None
            self._secrets.clear()
            path = self.directory.resolve()
            if path.is_relative_to(PRIVATE_ROOT.resolve()) and path.name.startswith("session-"):
                shutil.rmtree(path, ignore_errors=True)

    def configure(self, key, client_factory=ElevenLabs):
        with self.lock:
            self.client = self.catalog = self.plan = None
            client = client_factory(key)
            if key.strip():
                self._secrets.append(SecretStr(key.strip()))
            catalog = client.catalog()
            self._check_secret_text(json.dumps(catalog))
            self.client, self.catalog = client, catalog
            return catalog

    def _check_secret_text(self, text):
        if any(secret.get_secret_value() in text for secret in self._secrets):
            raise ValueError("A session credential was detected in content; remove it before saving or exporting")

    def edit(self, raw):
        self._check_secret_text(raw)
        if len(raw) > 2_000_000:
            raise ValueError("Package JSON is too large")
        try:
            package = ContentPackage.model_validate_json(raw)
        except ValueError:
            raise ValueError("Invalid package: check IDs, levels, answer keys, speaker turns and transcript hashes") from None
        with self.lock:
            old = {x.id: x for x in self.package.items}
            for item in package.items:
                item.review = Review()
                # Imported JSON cannot read arbitrary local files or assert paid output provenance.
                prior = old.get(item.id)
                if prior and item.model_dump(exclude={"review"}) == prior.model_dump(exclude={"review"}):
                    continue
                item.audio = None
                item.audio_sha256 = None
                item.passage.audio_asset_id = None
                item.recording = Recording()
                item.content_version = max(item.content_version, prior.content_version + 1 if prior else 1)
            self.package = package
            self.plan = None
            self.ledger["pilot_approval"] = None
            self.save()

    def _fingerprint(self, item, model, voices):
        data = [item.id, item.content_version, [t.model_dump() for t in item.turns], model, voices]
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def preflight(self, model, voices, budget, action="pilot", selected=None, acknowledge_uncertain=False):
        with self.lock:
            self.plan = None
            self._check_secret_text(json.dumps([model, voices]))
            if not self.client or not self.catalog:
                raise ValueError("Check your own API credentials first; no owner key is used")
            if model not in {m["model_id"] for m in self.catalog["models"]}:
                raise ValueError("Choose a model available to your account; Text to Dialogue support may vary")
            available = {v["voice_id"] for v in self.catalog["voices"]}
            if not isinstance(voices, dict) or not voices or len(voices) > 10 or any(not isinstance(v, str) or v not in available for v in voices.values()) or len(set(voices.values())) != len(voices):
                raise ValueError("Choose distinct available voices for all speakers (maximum ten)")
            budget = int(budget)
            if not 0 < budget <= 100_000:
                raise ValueError("Set an explicit total character budget from 1 to 100000")
            items = self.package.items
            if not items:
                raise ValueError("Import at least one dialogue")
            config = hashlib.sha256(json.dumps([model, voices], sort_keys=True).encode()).hexdigest()
            if action == "pilot":
                candidates = items[:1]
            elif action == "batch":
                if self.ledger["pilot_approval"] != config:
                    raise ValueError("Generate and listen to the pilot, then approve these voices before the batch")
                candidates = items
            elif action == "selected":
                candidates = [x for x in items if x.id == selected]
                if not candidates:
                    raise ValueError("Select an existing item")
                if candidates[0] is not items[0] and self.ledger["pilot_approval"] != config:
                    raise ValueError("Approve the pilot voices before generating other items")
            elif action == "audition":
                from .preset_bank import Turn
                from .dialogue_authoring import DialogueDraft, DraftQuestion, materialize
                sample = materialize(DialogueDraft(
                    topic="Voice audition", orientation_en="Voice audition only; not an assessment item.",
                    speakers={s: s for s in voices},
                    turns=[Turn(speaker=s, text="Здравствуйте! Сегодня хорошая погода.") for s in voices],
                    questions=[DraftQuestion(stem_en="What is the weather like today?",
                                             choices={"A": "Good", "B": "Rainy", "C": "Snowy", "D": "Windy"},
                                             correct_key="A", rationale_en="The speakers say the weather is good.",
                                             evidence_ru="Сегодня хорошая погода.")]), "voice_audition")
                candidates = [sample]
            else:
                raise ValueError("Unknown generation action")
            entries, count = [], 0
            for item in candidates:
                if item.passage.language != "ru" or item.passage.skill != "listening" or not item.turns:
                    raise ValueError("The dialogue workshop currently accepts Russian listening items with turns")
                if any(t.speaker not in voices for t in item.turns):
                    raise ValueError("Assign a voice to every speaker identifier")
                chars = sum(len(t.text) for t in item.turns)
                if chars > 2000:
                    raise ValueError(f"{item.id}: shorten to at most 2000 characters before generation")
                fingerprint = self._fingerprint(item, model, voices)
                old = self.ledger["attempts"].get(item.id, {})
                if old.get("status") == "succeeded" and old.get("fingerprint") == fingerprint and action in {"batch", "pilot"}:
                    continue
                if old.get("count", 0) >= 3:
                    raise ValueError(f"{item.id}: maximum three paid attempts reached")
                if old.get("status") in {"uncertain", "inflight"} and not acknowledge_uncertain:
                    raise ValueError(f"{item.id}: outcome uncertain. Check provider history and explicitly acknowledge possible duplicate charges")
                entries.append({"id": item.id, "item": item.model_copy(deep=True), "fingerprint": fingerprint, "characters": chars})
                count += chars
            if self.ledger["spent_characters"] + count > budget:
                raise ValueError("Character budget would be exceeded, including prior failed/uncertain reservations")
            self.plan = {"entries": entries, "model": model, "voices": dict(voices), "budget": budget,
                         "characters": count, "config": config, "action": action}
            return {"model": model, "voices": voices, "characters_this_run": count,
                    "reserved_so_far": self.ledger["spent_characters"], "total_character_limit": budget,
                    "usage": "Input characters, not a dollar/credit cap. Credits depend on model, voice rates and plan. API regenerations may be charged. Failed/uncertain requests stay reserved.",
                    "scripts": [{"id": e["id"], "turns": [t.model_dump() for t in e["item"].turns]} for e in entries]}

    def generate(self):
        if not self.lock.acquire(blocking=False):
            raise ValueError("A request is already in progress")
        try:
            plan, self.plan = self.plan, None  # consume once, before any network request
            if plan is None or self.client is None:
                raise ValueError("Review a new preflight before each paid run")
            completed = []
            for entry in plan["entries"]:
                item = entry["item"]
                previous = self.ledger["attempts"].get(item.id, {})
                attempt = {"fingerprint": entry["fingerprint"], "count": previous.get("count", 0) + 1,
                           "status": "inflight", "characters": entry["characters"], "time": now(),
                           "model": plan["model"], "voices": plan["voices"], "config": plan["config"]}
                self.ledger["spent_characters"] += entry["characters"]
                self.ledger["attempts"][item.id] = attempt
                self.save()  # reserve durably before sending; crash => uncertain on reload
                try:
                    audio = self.client.dialogue(item.turns, plan["voices"], plan["model"])
                    digest = hashlib.sha256(audio).hexdigest()
                    name = f"audio/{item.id}-{digest[:16]}.mp3"
                    target = self.directory / name
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes(audio)
                    item.passage.audio_asset_id = f"audio_{item.id}"
                    provider_name = getattr(self.client, "provider_name", "NONPRODUCTION MOCK")
                    item.audio = AudioAsset(id=item.passage.audio_asset_id, path=name, content_hash=digest,
                                            transcript_hash=item.passage.content_hash, engine=provider_name,
                                            license="Redistribution rights pending curator review; see recording metadata", validated=False)
                    item.audio_sha256 = digest
                    item.review = Review()
                    item.recording = Recording(provider=provider_name, model=plan["model"], voice_ids=plan["voices"],
                                               generated_at=now(), account_tier=str(self.catalog["account"].get("tier", "unknown")))
                    if item.id != "voice_audition":
                        self.package.items = [item if x.id == item.id else x for x in self.package.items]
                    attempt.update(status="succeeded", path=name)
                    completed.append(item.id)
                    self.save()
                except Exception as exc:
                    attempt["status"] = "failed" if isinstance(exc, ProviderError) and not exc.uncertain else "uncertain"
                    self.save()
                    message = str(exc) if isinstance(exc, ProviderError) else "Output could not be saved; check provider history before retrying."
                    return f"Saved {len(completed)} clips this run. Stopped at {item.id}: {message} Earlier successes are preserved."
            return f"Saved {len(completed)} clips. All remain drafts; export successful work before closing this session."
        finally:
            self.lock.release()

    def approve_voices(self):
        with self.lock:
            pilot = self.package.items[0]
            attempt = self.ledger["attempts"].get(pilot.id, {})
            if attempt.get("status") != "succeeded" or not pilot.audio:
                raise ValueError("Generate and listen to the first pilot before approving voices")
            self.ledger["pilot_approval"] = attempt["config"]
            self.save()

    def preview(self, item_id):
        with self.lock:
            entry = self.ledger["attempts"].get(item_id, {})
            if entry.get("status") != "succeeded":
                raise ValueError("No successful recording for this item")
            data = local_asset(self.directory, entry.get("path")).read_bytes()
            return '<audio controls src="data:audio/mpeg;base64,' + base64.b64encode(data).decode() + '"></audio>'

    def export(self):
        with self.lock:
            self._check_secret_text(self.package.model_dump_json() + json.dumps(self.ledger))
            out = io.BytesIO()
            package = self.package.model_copy(deep=True)
            for item in package.items:
                item.review = Review()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("package.json", package.model_dump_json(indent=2))
                archive.writestr("ledger.json", json.dumps(self.ledger, indent=2))
                for item in package.items:
                    if item.audio:
                        path = local_asset(self.directory, item.audio.path)
                        archive.write(path, item.audio.path)
                audition = self.ledger["attempts"].get("voice_audition", {})
                if audition.get("status") == "succeeded":
                    path = local_asset(self.directory, audition.get("path"))
                    archive.write(path, audition["path"])
            if out.tell() > 25_000_000:
                raise ValueError("Export exceeds 25 MB; use the local workshop CLI")
            return out.getvalue()
