from __future__ import annotations

import copy
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
from .topics import canonicalize_topic
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
        audio_available: Callable[[AudioAsset], bool] | None = None,
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
        self.passage_ids_by_skill: dict[str, set[str]] = {"reading": set(), "listening": set()}
        self.passage_ids_by_language_skill: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.question_ids_by_skill: dict[str, set[str]] = {"reading": set(), "listening": set()}
        self.topics_by_skill: dict[str, set[str]] = {"reading": set(), "listening": set()}
        self.topics_by_language_skill: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.passage_origin: dict[str, str] = {}
        self._loaded = False
        self._lock = threading.RLock()
        self.on_commit = on_commit
        self.audio_available = audio_available
        self.last_commit_result: Any | None = None
        self.load_warnings: list[str] = []
        self._active_cache: dict[tuple[str, str | None], tuple[PassageItem, ...]] = {}
        self._health_cache: dict[str | None, dict[str, Any]] = {}

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
                        if item.id in self.passages:
                            raise ValueError(f"duplicate passage id {item.id}; existing item was preserved")
                        self.passages[item.id] = item
                        self.passage_origin[item.id] = "generated_bank" if source == self.writable_path else "starter_bank"
                    elif kind == "question":
                        item = QuestionItem.model_validate(data)
                        if item.id in self.questions:
                            raise ValueError(f"duplicate question id {item.id}; existing item was preserved")
                        if source == self.writable_path and self.passage_origin.get(item.passage_id) != "generated_bank":
                            raise ValueError(
                                f"generated question {item.id} cannot attach to non-generated passage {item.passage_id}"
                            )
                        self.questions[item.id] = item
                    elif kind == "audio":
                        item = AudioAsset.model_validate(data)
                        if item.id in self.audio_assets:
                            raise ValueError(f"duplicate audio id {item.id}; existing item was preserved")
                        self.audio_assets[item.id] = item
                    elif kind == "validation":
                        if data["id"] in self.validation_reports:
                            raise ValueError(f"duplicate validation id {data['id']}; existing report was preserved")
                        self.validation_reports[data["id"]] = data
                except Exception as exc:
                    message = f"Invalid item-bank record in {source} at line {line_number}: {exc}"
                    if required:
                        raise ItemBankError(message) from exc
                    # A malformed generated overlay must never prevent the validated
                    # starter bank from serving users. Invalid overlay records are
                    # excluded from indexing and surfaced through bank health status.
                    self.load_warnings.append(message)

    def _invalidate_runtime_caches(self) -> None:
        self._active_cache.clear()
        self._health_cache.clear()

    def _reindex(self) -> None:
        self._invalidate_runtime_caches()
        self.questions_by_passage = defaultdict(list)
        self.passage_ids_by_skill = {"reading": set(), "listening": set()}
        self.passage_ids_by_language_skill = defaultdict(set)
        self.question_ids_by_skill = {"reading": set(), "listening": set()}
        self.topics_by_skill = {"reading": set(), "listening": set()}
        self.topics_by_language_skill = defaultdict(set)
        for passage_id, original in list(self.passages.items()):
            canonical_topic = canonicalize_topic(original.topic, original.subtopic, original.genre)
            passage = original if canonical_topic == original.topic else original.model_copy(update={"topic": canonical_topic})
            if passage is not original:
                self.passages[passage_id] = passage
            self.passage_ids_by_skill[passage.skill].add(passage.id)
            self.passage_ids_by_language_skill[(passage.language, passage.skill)].add(passage.id)
            self.topics_by_skill[passage.skill].add(passage.topic)
            self.topics_by_language_skill[(passage.language, passage.skill)].add(passage.topic)
        for question in self.questions.values():
            self.questions_by_passage[question.passage_id].append(question)
            passage = self.passages.get(question.passage_id)
            if passage is not None:
                self.question_ids_by_skill[passage.skill].add(question.id)
        for questions in self.questions_by_passage.values():
            questions.sort(key=lambda q: q.id)

    def load(self) -> "ItemBank":
        with self._lock:
            if self._loaded:
                return self
            for source in self.paths:
                # Every immutable starter source is required. Only the writable
                # generated overlay is optional on a clean first launch.
                required = len(self.paths) == 1 or source != self.writable_path
                self._load_path(source, required=required)
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
            self.passage_ids_by_skill = {"reading": set(), "listening": set()}
            self.passage_ids_by_language_skill = defaultdict(set)
            self.question_ids_by_skill = {"reading": set(), "listening": set()}
            self.topics_by_skill = {"reading": set(), "listening": set()}
            self.topics_by_language_skill = defaultdict(set)
            self.passage_origin.clear()
            self.load_warnings.clear()
            self._loaded = False
        return self.load()

    def validate_operational_bank(self) -> list[str]:
        errors: list[str] = []
        seen_hashes: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        for passage in self.passages.values():
            questions = self.questions_by_passage.get(passage.id, [])
            passage_report = validate_passage(passage, questions)
            if passage_report.status != "accepted":
                errors.append(f"{passage.id}: {', '.join(passage_report.failure_reasons)}")
            if passage.content_hash != content_hash(passage.passage_ru):
                errors.append(f"{passage.id}: content hash mismatch")
            bank_key = (passage.language, passage.skill)
            for other_hash, other_id in seen_hashes[bank_key].items():
                if passage.duplicate_detection_hash == other_hash or near_duplicate(passage.passage_ru, self.passages[other_id].passage_ru):
                    errors.append(f"{passage.id}: duplicate or near-duplicate {passage.skill} passage {other_id}")
            seen_hashes[bank_key][passage.duplicate_detection_hash] = passage.id
            audio_error = self._audio_relationship_error(passage)
            if audio_error:
                errors.append(f"{passage.id}: {audio_error}")
            for question in questions:
                report = validate_question(question, passage)
                if report.status != "accepted":
                    errors.append(f"{question.id}: {', '.join(report.failure_reasons + report.ambiguity_flags)}")
        return errors

    def _resolve_audio_path(self, asset: AudioAsset) -> Path | None:
        if not asset.path:
            return None
        audio_path = Path(asset.path)
        if not audio_path.is_absolute():
            candidates = [Path.cwd() / audio_path, self.path.parent.parent / audio_path]
            audio_path = next((candidate for candidate in candidates if candidate.exists()), candidates[-1])
        return audio_path

    def _audio_relationship_error(self, passage: PassageItem, supplied_asset: AudioAsset | None = None) -> str | None:
        """Enforce the skill/audio contract at the operational-bank boundary."""
        if passage.skill == "reading":
            if passage.audio_asset_id is not None or passage.audio_duration_seconds is not None or passage.voice_metadata:
                return "reading passage must not reference audio metadata"
            if supplied_asset is not None:
                return "reading passage must not include an audio asset"
            return None

        asset = supplied_asset or self.audio_assets.get(passage.audio_asset_id or "")
        if not passage.audio_asset_id:
            return "listening passage is missing audio_asset_id"
        if asset is None or asset.id != passage.audio_asset_id:
            return "listening passage references a missing or mismatched audio asset"
        if not asset.validated:
            return "listening audio asset is not validated"
        if asset.transcript_hash != content_hash(passage.passage_ru):
            return "listening audio transcript hash does not match the passage"
        audio_path = self._resolve_audio_path(asset)
        if audio_path is None or not audio_path.exists() or audio_path.stat().st_size <= 0:
            if self.audio_available is not None:
                try:
                    if self.audio_available(asset):
                        return None
                except Exception:
                    pass
            return "listening audio file is missing or empty"
        return None

    def active_passages(self, skill: str, language: str | None = None) -> list[PassageItem]:
        if skill not in {"reading", "listening"}:
            raise ItemBankError(f"Unsupported skill: {skill}")
        cache_key = (skill, language)
        cached = self._active_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        active: list[PassageItem] = []
        passage_ids = (
            self.passage_ids_by_language_skill[(language, skill)]
            if language is not None
            else self.passage_ids_by_skill[skill]
        )
        for passage_id in passage_ids:
            passage = self.passages[passage_id]
            if passage.status != "active" or passage.validation_status != "accepted":
                continue
            questions = self.questions_by_passage.get(passage.id, [])
            if len(questions) != len(passage.question_ids):
                continue
            if validate_passage(passage, questions).status != "accepted":
                continue
            if any(validate_question(question, passage).status != "accepted" for question in questions):
                continue
            if self._audio_relationship_error(passage):
                continue
            active.append(passage)
        self._active_cache[cache_key] = tuple(active)
        return list(active)

    def topics_for_skill(self, skill: str, language: str | None = None) -> list[str]:
        if skill not in self.topics_by_skill:
            raise ItemBankError(f"Unsupported skill: {skill}")
        if language is not None:
            return sorted(self.topics_by_language_skill[(language, skill)])
        return sorted(self.topics_by_skill[skill])

    def health_summary(self, language: str | None = None) -> dict[str, Any]:
        """Return source-aware and skill-aware bank health metrics.

        Terminology:
        - starter: immutable validated content bundled with the application;
        - generated: accepted AI-authored/imported content in the writable overlay;
        - ready/operational: content from either source that currently passes every
          validation and, for Listening, has a usable validated audio asset.

        Selecting or answering an item never changes these counts. Only an
        accepted fresh-generation commit or an explicit import/merge can add to
        the generated overlay.
        """
        cached = self._health_cache.get(language)
        if cached is not None:
            return copy.deepcopy(cached)
        included_ids = {
            pid for pid, passage in self.passages.items()
            if language is None or passage.language == language
        }
        starter_ids = {pid for pid in included_ids if self.origin_for(pid) == "starter_bank"}
        generated_ids = {pid for pid in included_ids if self.origin_for(pid) == "generated_bank"}
        summary: dict[str, Any] = {
            "passages": len(included_ids),
            "questions": sum(len(self.questions_by_passage.get(pid, [])) for pid in included_ids),
            "audio_assets": len({
                self.passages[pid].audio_asset_id for pid in included_ids
                if self.passages[pid].audio_asset_id in self.audio_assets
            }),
            "starter_passages": len(starter_ids),
            "starter_questions": sum(len(self.questions_by_passage.get(pid, [])) for pid in starter_ids),
            "generated_passages": len(generated_ids),
            "generated_questions": sum(len(self.questions_by_passage.get(pid, [])) for pid in generated_ids),
            "load_warnings": len(self.load_warnings),
        }
        for skill in ("reading", "listening"):
            passage_ids = (
                self.passage_ids_by_language_skill[(language, skill)]
                if language is not None
                else self.passage_ids_by_skill[skill]
            )
            starter_skill_ids = {pid for pid in passage_ids if self.origin_for(pid) == "starter_bank"}
            generated_skill_ids = {pid for pid in passage_ids if self.origin_for(pid) == "generated_bank"}
            ready = self.active_passages(skill, language)
            ready_ids = {passage.id for passage in ready}
            ready_starter_ids = ready_ids & starter_skill_ids
            ready_generated_ids = ready_ids & generated_skill_ids

            def question_count(ids: set[str]) -> int:
                return sum(len(self.questions_by_passage.get(pid, [])) for pid in ids)

            def ilr_counts(ids: set[str]) -> dict[str, int]:
                question_ids = {
                    question.id
                    for pid in ids
                    for question in self.questions_by_passage.get(pid, [])
                }
                return {
                    level: sum(1 for qid in question_ids if self.questions[qid].target_ilr == level)
                    for level in ("0", "0+", "1", "1+", "2", "2+", "3")
                }

            skill_data = {
                # Backward-compatible total/index fields.
                "passages": len(passage_ids),
                "questions": question_count(set(passage_ids)),
                "generated_passages": len(generated_skill_ids),
                "generated_questions": question_count(generated_skill_ids),
                "operational_passages": len(ready_ids),
                "operational_questions": question_count(ready_ids),
                "topics": len(self.topics_for_skill(skill, language)),
                "ilr_question_counts": ilr_counts(ready_ids),
                # Explicit source-aware fields used by the UI.
                "starter_passages": len(starter_skill_ids),
                "starter_questions": question_count(starter_skill_ids),
                "saved_ai_passages": len(generated_skill_ids),
                "saved_ai_questions": question_count(generated_skill_ids),
                "ready_passages": len(ready_ids),
                "ready_questions": question_count(ready_ids),
                "ready_starter_passages": len(ready_starter_ids),
                "ready_starter_questions": question_count(ready_starter_ids),
                "ready_ai_passages": len(ready_generated_ids),
                "ready_ai_questions": question_count(ready_generated_ids),
                "ready_ilr_question_counts": ilr_counts(ready_ids),
                "saved_ai_ilr_question_counts": ilr_counts(generated_skill_ids),
            }
            if skill == "listening":
                linked_audio_ids = {
                    self.passages[pid].audio_asset_id for pid in passage_ids
                    if self.passages[pid].audio_asset_id
                }
                generated_linked_audio_ids = {
                    self.passages[pid].audio_asset_id for pid in generated_skill_ids
                    if self.passages[pid].audio_asset_id
                }
                ready_audio_ids = {p.audio_asset_id for p in ready if p.audio_asset_id}
                skill_data.update({
                    "audio_assets": len(linked_audio_ids),
                    "generated_audio_assets": len(generated_linked_audio_ids),
                    "saved_ai_audio_assets": len(generated_linked_audio_ids),
                    "missing_or_invalid_audio": sum(
                        1 for pid in passage_ids if self._audio_relationship_error(self.passages[pid])
                    ),
                    "operational_audio_assets": len(ready_audio_ids),
                    "ready_audio_assets": len(ready_audio_ids),
                })
            summary[skill] = skill_data
        summary["cross_skill_related_pairs"] = self._cross_skill_related_pair_count(language)
        self._health_cache[language] = copy.deepcopy(summary)
        return summary

    def _cross_skill_related_pair_count(self, language: str | None = None) -> int:
        """Count explicit/exact cross-skill relationships without an O(n²) status scan."""
        pairs: set[tuple[str, str]] = set()
        for passage in self.passages.values():
            if language is not None and passage.language != language:
                continue
            related = passage.provenance.get("cross_skill_related_passage_id")
            if related and related in self.passages and self.passages[related].skill != passage.skill:
                pairs.add(tuple(sorted((passage.id, related))))

        reading_ids = self.passage_ids_by_language_skill[(language, "reading")] if language else self.passage_ids_by_skill["reading"]
        listening_ids = self.passage_ids_by_language_skill[(language, "listening")] if language else self.passage_ids_by_skill["listening"]
        reading_by_hash = {self.passages[pid].duplicate_detection_hash: pid for pid in reading_ids}
        for pid in listening_ids:
            passage = self.passages[pid]
            related = reading_by_hash.get(passage.duplicate_detection_hash)
            if related:
                pairs.add(tuple(sorted((pid, related))))
        return len(pairs)

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

    def duplicate_of(self, passage: PassageItem, same_skill_only: bool = True) -> str | None:
        for existing in self.passages.values():
            if existing.language != passage.language:
                continue
            if same_skill_only and existing.skill != passage.skill:
                continue
            if existing.content_hash == passage.content_hash or existing.duplicate_detection_hash == passage.duplicate_detection_hash:
                return existing.id
            if near_duplicate(existing.passage_ru, passage.passage_ru):
                return existing.id
        return None

    def cross_skill_duplicate_of(self, passage: PassageItem) -> str | None:
        for existing in self.passages.values():
            if existing.language != passage.language:
                continue
            if existing.skill == passage.skill:
                continue
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
            audio_error = self._audio_relationship_error(passage, audio_asset)
            if audio_error:
                raise ItemBankError(audio_error)
            duplicate = self.duplicate_of(passage, same_skill_only=True)
            if duplicate:
                raise ItemBankError(f"Generated passage duplicates existing {passage.skill} passage {duplicate}.")
            cross_skill_duplicate = self.cross_skill_duplicate_of(passage)
            if cross_skill_duplicate:
                passage.provenance["cross_skill_related_passage_id"] = cross_skill_duplicate
                passage.provenance["cross_skill_policy"] = "stored separately; repeat exposure suppressed across skills"
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
        language: str = "ru",
    ) -> AdaptiveSelection:
        seen_content_hashes = {
            self.passages[passage_id].content_hash
            for passage_id in seen_passages
            if passage_id in self.passages
        }
        seen_duplicate_hashes = {
            self.passages[passage_id].duplicate_detection_hash
            for passage_id in seen_passages
            if passage_id in self.passages
        }
        eligible_passages = [
            passage for passage in self.active_passages(skill, language)
            if passage.id in seen_passages
            or (
                passage.content_hash not in seen_content_hashes
                and passage.duplicate_detection_hash not in seen_duplicate_hashes
            )
        ]
        return select_passage(
            eligible_passages, self.questions_by_passage, estimate, mode, target_level,
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
