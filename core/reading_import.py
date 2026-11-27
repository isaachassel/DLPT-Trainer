"""Lossless adapter for the authentic reading interchange pack; never approves."""
from datetime import date
from hashlib import sha256
from urllib.parse import urlsplit

from .constants import ILR_THETA, LETTERS
from .models import GenerationMetadata, PassageItem, QuestionItem
from .preset_bank import ContentItem, ContentPackage, Review, reject_secret_fields, validate_item
from .validation import content_hash, target_unit_count

SKILL_MAP = {
    "explicit_cause": "cause and effect", "attributed_cause": "cause and effect",
    "detail_paraphrase": "prominent detail", "scope": "main idea",
    "frequency_qualifier": "prominent detail", "rule_application": "inference",
    "supported_inference": "inference", "conditional_claim": "relationship of ideas",
    "author_attitude": "tone or attitude", "function_of_example": "relationship of ideas",
    "planned_vs_actual": "prominent detail", "purpose": "speaker/writer intent",
    "reference_tracking": "reference", "main_idea": "main idea",
    "vocabulary_in_context": "meaning from context",
}


def public_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        return (parts.scheme in {"http", "https"} and bool(parts.hostname)
                and not parts.username and not parts.password
                and not any(c.isspace() for c in value))
    except ValueError:
        return False


def convert_reading_pack(data: dict, version: int = 1) -> ContentPackage:
    reject_secret_fields(data)
    if (data.get("schema_version") != "1.0.0" or
            data.get("content_status") != "teacher_review_draft" or
            data.get("passage_language") != "ru" or data.get("question_language") != "en"):
        raise ValueError("Expected the Russian teacher-review reading interchange format 1.0.0")
    if not data.get("pack_id") or not 1 <= len(data.get("passages", [])) <= 100:
        raise ValueError("A named pack with 1–100 passages is required")
    date.fromisoformat(data["created_date"])
    items, all_ids = [], set()
    for number, source in enumerate(data["passages"], 1):
        if (source["language"] != "ru" or source["modality"] != "reading" or
                source["diagnostic_eligible"] is not False or
                source["review_status"] != "draft_pending_teacher_review" or
                source["calibration_status"] != "uncalibrated" or source["human_reviewer"] is not None):
            raise ValueError("Only unapproved, uncalibrated Russian reading drafts are accepted")
        if not source.get("family_id"):
            raise ValueError("Stable passage family_id is required")
        ids = [source["id"], *[q["id"] for q in source["questions"]]]
        if len(ids) != len(set(ids)) or all_ids.intersection(ids):
            raise ValueError("Duplicate passage or question ID")
        all_ids.update(ids)
        paragraphs = {p["id"]: p["text"] for p in source["paragraphs"]}
        if len(paragraphs) != len(source["paragraphs"]) or not all(paragraphs.values()):
            raise ValueError("Paragraph IDs must be unique and text must be present")
        text = source["text"]
        if text != "\n\n".join(paragraphs.values()):
            raise ValueError("Text must exactly match the original ordered paragraphs")
        if sha256(text.encode("utf-8")).hexdigest() != source["text_sha256"]:
            raise ValueError("Exact source text checksum mismatch")
        date.fromisoformat(source["publication_date"])
        provenance = source["source"]
        for field in ("title", "publisher", "author", "archive_publisher", "license", "license_basis"):
            if not provenance.get(field):
                raise ValueError(f"Missing source {field}")
        for field in ("original_url", "archive_revision_url", "license_url", "license_evidence_url"):
            if not public_url(provenance.get(field, "")):
                raise ValueError(f"Invalid source {field}")
        if source["authenticity"]["kind"] != "published_russian_verbatim_excerpt":
            raise ValueError("This adapter only imports verbatim published excerpts")
        metadata = GenerationMetadata(provider="contributor import", model="unspecified question authoring",
            prompt_version=data["pack_id"], generated_at=data["created_date"] + "T00:00:00Z",
            authoring_notes="Published source text preserved. Newly authored questions; teacher review pending.")
        level = source["provisional_ilr"]
        questions = []
        for q in source["questions"]:
            options = q["options"]
            if len(options) != 4 or {o["id"] for o in options} != set(LETTERS):
                raise ValueError("Exactly four stable A–D option IDs are required")
            if q["correct_option_id"] not in LETTERS or not all(o["rationale_en"].strip() for o in options):
                raise ValueError("A valid answer key and all distractor rationales are required")
            if q["scoring"] != {"points": 1, "partial_credit": False}:
                raise ValueError("Only one-point single-answer questions are supported")
            if not q["evidence"] or any(not e["quote_ru"] or e["quote_ru"] not in
                    paragraphs.get(e["paragraph_id"], "") for e in q["evidence"]):
                raise ValueError("Evidence must occur exactly in its referenced paragraph")
            questions.append(QuestionItem(id=q["id"], passage_id=source["id"],
                stem_en=q["stem_en"], choices={o["id"]: o["text_en"] for o in options},
                correct_key=q["correct_option_id"], rationale_en=q["explanation_en"],
                # Native validator accepts one contiguous quote; every supporting
                # span, paragraph reference and distractor rationale survives below.
                evidence_ru=q["evidence"][0]["quote_ru"], question_type=SKILL_MAP[q["skill"]],
                target_ilr=level, provisional_difficulty=ILR_THETA[level], generation=metadata,
                created_at=metadata.generated_at,
                answer_position_metadata={"source_skill": q["skill"],
                                          "stable_option_ids": {k: k for k in LETTERS}}))
        digest = content_hash(text)
        passage = PassageItem(id=source["id"], family_id=source["family_id"], skill="reading", language="ru",
            target_ilr=level, provisional_difficulty=ILR_THETA[level], genre="news article",
            topic=source["topic"], subtopic="Historical published news", orientation_en=source["orientation_en"],
            passage_ru=text, source_type="authentic/open-licensed", license=provenance["license"],
            provenance={**{f"source_{k}": v for k, v in provenance.items()},
                "publication_date": source["publication_date"], "learner_label": f"Reading passage {number}",
                "attribution": source["attribution"], "selection": source["authenticity"]["selection"],
                "modifications": " ".join(source["authenticity"]["transformations"]),
                "authenticity_notes": source["authenticity"]["notes"], "pack_id": data["pack_id"],
                "provisional_ilr": level, "difficulty_rationale": source["level_rationale"]},
            word_count=target_unit_count(text, "ru"), question_ids=[q.id for q in questions],
            content_hash=digest, duplicate_detection_hash=digest, generation=metadata,
            created_at=metadata.generated_at)
        item = ContentItem(id=source["id"], content_version=version, passage=passage, questions=questions,
            authoring_record=source, review=Review(notes="Teacher-review draft. Verify rights, authenticity, "
                "difficulty, unique best answers, distractors and exact evidence. Not calibrated."))
        # Structural acceptance is separate from the required curator approval.
        validate_item(item, None)
        items.append(item)
    return ContentPackage(items=items)
