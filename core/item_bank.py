from __future__ import annotations

import json
import random
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .adaptive import select_passage
from .constants import LETTERS
from .models import AdaptiveSelection, AudioAsset, PassageItem, QuestionItem, ValidationReport
from .storage import atomic_write_text
from .validation import content_hash, near_duplicate, validate_passage, validate_question


class ItemBankError(RuntimeError):
    pass


class ItemBank:
    """In-memory indexed bank backed by an immutable starter file and writable overlay."""

    def __init__(
        self,
        path: str | Path | Sequence[str | Path],
        writable_path: str | Path | None = None,
        on_commit: Callable[[Path], Any] | None = None,
    ):
        if isinstance(path, (str, Path)):
            self.paths = [Path(path)]
        else:
            self.paths = [Path(item) for item in path]
        self.path = self.paths[0]
        self.writable_path = Path(writable_path) if writable_path else (self.paths[-1] if len(self.paths) > 1 else self.path)
        self.passages: dict[str, PassageItem] = {}
        self.questions: dict[str, QuestionItem] = {}
        self.audio_assets: dict[str, AudioAsset] = {}
        self.validation_reports: dict[str, dict] = {}
        self.questions_by_passage: dict[str, list[QuestionItem]] = defaultdict(list)
        self.passage_origin: dict[str, str] = {}
        self._loaded = False
        self._lock = threading.RLock()
        self.on_commit = on_commit
        self.last_commit_result: Any | None = None
        self.load_warnings: list[str] = []

    def _load_path(self, source: Path, required: bool) -> None:
        if not source.exists():
            if required:
                raise ItemBankError(f"Item bank not found: {source}")
            return
        with source.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                    kind = record["kind"]
                    data = record["data"]
                    if kind == "passage":
                        item = PassageItem.model_validate(data)
                        self.passages[item.id] = item
                        self.passage_origin[item.id] = "starter_bank" if source == self.paths[0] else "generated_bank"
                    elif kind == "question":
                        item = QuestionItem.model_validate(data)
                        self.questions[item.id] = item
                    elif kind == "audio":
                        item = AudioAsset.model_validate(data)
                        self.audio_assets[item.id] = item
                    elif kind == "validation":
                        self.validation_reports[data["id"]] = data
                except Exception as exc:
                    message = f"Invalid item-bank record in {source} at line {line_number}: {exc}"
                    if required:
                        raise ItemBankError(message) from exc
                    # A malformed generated overlay must never prevent the validated
                    # starter bank from serving users. Invalid overlay records are
                    # excluded from indexing and surfaced through bank health status.
                    self.load_warnings.append(message)

    def _reindex(self) -> None:
        self.questions_by_passage = defaultdict(list)
        for question in self.questions.values():
            self.questions_by_passage[question.passage_id].append(question)
        for questions in self.questions_by_passage.values():
            questions.sort(key=lambda q: q.id)

    def load(self) -> "ItemBank":
        with self._lock:
            if self._loaded:
                return self
            for index, source in enumerate(self.paths):
                self._load_path(source, required=index == 0)
            self._reindex()
            self._loaded = True
        return self

    def reload(self) -> "ItemBank":
        """Reload starter and generated overlays in place.

        The object identity is preserved so services that hold a reference to
        the bank immediately see imported or remotely restored generated items.
        """

        with self._lock:
            self.passages.clear()
            self.questions.clear()
            self.audio_assets.clear()
            self.validation_reports.clear()
            self.questions_by_passage = defaultdict(list)
            self.passage_origin.clear()
            self.load_warnings.clear()
            self._loaded = False
        return self.load()

    def validate_operational_bank(self) -> list[str]:
        errors: list[str] = []
        seen_hashes: dict[str, str] = {}
        for passage in self.passages.values():
            questions = self.questions_by_passage.get(passage.id, [])
            passage_report = validate_passage(passage, questions)
            if passage_report.status != "accepted":
                errors.append(f"{passage.id}: {', '.join(passage_report.failure_reasons)}")
            if passage.content_hash != content_hash(passage.passage_ru):
                errors.append(f"{passage.id}: content hash mismatch")
            for other_hash, other_id in seen_hashes.items():
                if passage.duplicate_detection_hash == other_hash or near_duplicate(passage.passage_ru, self.passages[other_id].passage_ru):
                    errors.append(f"{passage.id}: duplicate or near-duplicate of {other_id}")
            seen_hashes[passage.duplicate_detection_hash] = passage.id
            for question in questions:
                report = validate_question(question, passage)
                if report.status != "accepted":
                    errors.append(f"{question.id}: {', '.join(report.failure_reasons + report.ambiguity_flags)}")
        return errors

    def active_passages(self, skill: str) -> list[PassageItem]:
        active: list[PassageItem] = []
        for passage in self.passages.values():
            if passage.skill != skill or passage.status != "active" or passage.validation_status != "accepted":
                continue
            questions = self.questions_by_passage.get(passage.id, [])
            if len(questions) != len(passage.question_ids):
                continue
            if validate_passage(passage, questions).status != "accepted":
                continue
            if any(validate_question(question, passage).status != "accepted" for question in questions):
                continue
            if passage.skill == "listening":
                if not passage.audio_asset_id or passage.audio_asset_id not in self.audio_assets:
                    continue
                audio_path = Path(self.audio_assets[passage.audio_asset_id].path)
                if not audio_path.is_absolute():
                    candidates = [Path.cwd() / audio_path, self.path.parent.parent / audio_path]
                    audio_path = next((candidate for candidate in candidates if candidate.exists()), candidates[-1])
                if not audio_path.exists() or audio_path.stat().st_size <= 0:
                    continue
            active.append(passage)
        return active

    def health_summary(self) -> dict[str, int]:
        return {
            "passages": len(self.passages),
            "questions": len(self.questions),
            "audio_assets": len(self.audio_assets),
            "generated_passages": sum(1 for passage_id in self.passages if self.origin_for(passage_id) == "generated_bank"),
            "generated_questions": sum(
                len(self.questions_by_passage.get(passage_id, []))
                for passage_id in self.passages
                if self.origin_for(passage_id) == "generated_bank"
            ),
            "load_warnings": len(self.load_warnings),
        }

    def get_passage(self, passage_id: str) -> PassageItem:
        try:
            return self.passages[passage_id]
        except KeyError as exc:
            raise ItemBankError(f"Unknown passage: {passage_id}") from exc

    def get_questions(self, passage_id: str) -> list[QuestionItem]:
        return [q.model_copy(deep=True) for q in self.questions_by_passage.get(passage_id, [])]

    def get_audio(self, audio_id: str | None) -> AudioAsset | None:
        if not audio_id:
            return None
        return self.audio_assets.get(audio_id)

    def origin_for(self, passage_id: str) -> str:
        return self.passage_origin.get(passage_id, "starter_bank")

    def duplicate_of(self, passage: PassageItem) -> str | None:
        for existing in self.passages.values():
            if existing.content_hash == passage.content_hash or existing.duplicate_detection_hash == passage.duplicate_detection_hash:
                return existing.id
            if near_duplicate(existing.passage_ru, passage.passage_ru):
                return existing.id
        return None

    def append_validated_bundle(
        self,
        passage: PassageItem,
        questions: list[QuestionItem],
        passage_report: ValidationReport,
        question_reports: list[ValidationReport],
        audio_asset: AudioAsset | None = None,
    ) -> Any | None:
        """Atomically append an accepted bundle and make it immediately selectable."""
        with self._lock:
            if passage_report.status != "accepted" or any(report.status != "accepted" for report in question_reports):
                raise ItemBankError("Only accepted validated content may enter the operational bank.")
            p_check = validate_passage(passage, questions)
            q_checks = [validate_question(question, passage) for question in questions]
            if p_check.status != "accepted" or any(report.status != "accepted" for report in q_checks):
                raise ItemBankError("The bundle failed deterministic validation immediately before persistence.")
            duplicate = self.duplicate_of(passage)
            if duplicate:
                raise ItemBankError(f"Generated passage duplicates existing passage {duplicate}.")
            if passage.id in self.passages or any(question.id in self.questions for question in questions):
                raise ItemBankError("Generated item IDs already exist in the bank.")

            records: list[dict] = [
                {"kind": "passage", "data": passage.model_dump(mode="json")},
                *({"kind": "question", "data": question.model_dump(mode="json")} for question in questions),
                {"kind": "validation", "data": passage_report.model_dump(mode="json")},
                *({"kind": "validation", "data": report.model_dump(mode="json")} for report in question_reports),
            ]
            if audio_asset is not None:
                records.append({"kind": "audio", "data": audio_asset.model_dump(mode="json")})
            new_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
            existing_text = self.writable_path.read_text(encoding="utf-8") if self.writable_path.exists() else ""
            atomic_write_text(self.writable_path, existing_text + new_text)

            self.passages[passage.id] = passage
            self.passage_origin[passage.id] = "generated_bank"
            for question in questions:
                self.questions[question.id] = question
            if audio_asset is not None:
                self.audio_assets[audio_asset.id] = audio_asset
            self.validation_reports[passage_report.id] = passage_report.model_dump(mode="json")
            for report in question_reports:
                self.validation_reports[report.id] = report.model_dump(mode="json")
            self._reindex()
            self.last_commit_result = None
            if self.on_commit is not None:
                try:
                    self.last_commit_result = self.on_commit(self.writable_path)
                except Exception as exc:
                    # Persistence metadata/remote mirroring must not roll back a
                    # bundle that has already been atomically committed locally.
                    self.last_commit_result = {"remote_synced": False, "note": f"Post-commit sync failed: {type(exc).__name__}."}
            return self.last_commit_result

    def select(
        self,
        skill: str,
        estimate,
        mode: str,
        target_level: str,
        seen_passages: set[str],
        seen_questions: set[str],
        topic_exposure: dict[str, int],
        genre_exposure: dict[str, int],
        question_type_exposure: dict[str, int],
        item_exposure: dict[str, int],
        allowed_topics: set[str] | None,
        preferred_competencies: set[str] | None,
        first_passage: bool,
        allowed_ilr_bands: set[str] | None = None,
        routing_band: str | None = None,
        selection_seed: str | None = None,
    ) -> AdaptiveSelection:
        return select_passage(
            self.active_passages(skill), self.questions_by_passage, estimate, mode, target_level,
            seen_passages, seen_questions, topic_exposure, genre_exposure,
            question_type_exposure, item_exposure, allowed_topics, preferred_competencies, first_passage,
            allowed_ilr_bands, routing_band, selection_seed,
        )


def shuffle_question(question: QuestionItem, rng: random.Random | None = None) -> QuestionItem:
    rng = rng or random.Random()
    original = [(letter, question.choices[letter]) for letter in LETTERS]
    shuffled = original.copy()
    rng.shuffle(shuffled)
    new_choices = {new_letter: text for new_letter, (_, text) in zip(LETTERS, shuffled)}
    original_correct_text = question.choices[question.correct_key]
    new_correct = next(letter for letter, text in new_choices.items() if text == original_correct_text)
    metadata = dict(question.answer_position_metadata)
    metadata.update({
        "original_correct_key": question.correct_key,
        "shuffled_correct_key": new_correct,
        "shuffle_map": {new_letter: old_letter for new_letter, (old_letter, _) in zip(LETTERS, shuffled)},
    })
    return question.model_copy(update={"choices": new_choices, "correct_key": new_correct, "answer_position_metadata": metadata})


def shuffle_question_to_key(question: QuestionItem, target_key: str, rng: random.Random | None = None) -> QuestionItem:
    """Shuffle choices while placing the correct answer at a bank-balancing target key."""
    if target_key not in LETTERS:
        raise ValueError("target_key must be A, B, C, or D")
    rng = rng or random.Random()
    correct_text = question.choices[question.correct_key]
    distractors = [(letter, text) for letter, text in question.choices.items() if letter != question.correct_key]
    rng.shuffle(distractors)
    remaining_keys = [letter for letter in LETTERS if letter != target_key]
    new_choices = {target_key: correct_text}
    shuffle_map = {target_key: question.correct_key}
    for new_key, (old_key, text) in zip(remaining_keys, distractors):
        new_choices[new_key] = text
        shuffle_map[new_key] = old_key
    new_choices = {letter: new_choices[letter] for letter in LETTERS}
    metadata = dict(question.answer_position_metadata)
    metadata.update({
        "original_correct_key": question.correct_key,
        "shuffled_correct_key": target_key,
        "shuffle_map": shuffle_map,
        "bank_balance_target": target_key,
    })
    return question.model_copy(update={"choices": new_choices, "correct_key": target_key, "answer_position_metadata": metadata})


def shuffled_bundle(questions: Iterable[QuestionItem], seed: str) -> list[QuestionItem]:
    rng = random.Random(seed)
    return [shuffle_question(question, rng) for question in questions]
