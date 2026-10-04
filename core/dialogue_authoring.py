"""Manual templates and optional BYO text authoring using the existing provider adapter."""
from uuid import uuid4
from pydantic import Field
from .models import StrictModel, PassageItem, QuestionItem, GenerationMetadata
from .preset_bank import ContentItem, Turn
from .validation import content_hash, target_unit_count
from .constants import ILR_THETA


class DraftQuestion(StrictModel):
    stem_en: str
    choices: dict[str, str]
    correct_key: str
    rationale_en: str
    evidence_ru: str


class DialogueDraft(StrictModel):
    topic: str
    orientation_en: str
    speakers: dict[str, str]
    turns: list[Turn] = Field(min_length=2, max_length=12)
    questions: list[DraftQuestion] = Field(min_length=1, max_length=3)


def materialize(draft, item_id, provider="manual", model="manual", language="ru", target_ilr="0+"):
    text = "\n".join(f"{t.speaker}: {t.text}" for t in draft.turns)
    metadata = GenerationMetadata(provider=provider, model=model, prompt_version="russian-dialogue-0plus-v1" if language == "ru" and target_ilr == "0+" else f"{language}-dialogue-{target_ilr}-v1",
                                  authoring_notes="Original draft; language, audio and ILR review pending.")
    questions = [QuestionItem(id=f"{item_id}_q{i}", passage_id=item_id, **q.model_dump(),
                              question_type="prominent detail", target_ilr=target_ilr, provisional_difficulty=ILR_THETA[target_ilr],
                              generation=metadata) for i, q in enumerate(draft.questions, 1)]
    passage = PassageItem(id=item_id, language=language, skill="listening", target_ilr=target_ilr, provisional_difficulty=ILR_THETA[target_ilr],
                          genre="dialogue", topic=draft.topic, subtopic=draft.topic, orientation_en=draft.orientation_en,
                          passage_ru=text, word_count=target_unit_count(text, language), question_ids=[q.id for q in questions],
                          content_hash=content_hash(text), duplicate_detection_hash=content_hash(text), generation=metadata,
                          provenance={"authoring": "Original AI-assisted draft; pending human review"})
    return ContentItem(id=item_id, passage=passage, questions=questions, speakers=draft.speakers, turns=draft.turns)


def author(key, model, topic):
    if not key.strip() or not model.strip() or not topic.strip():
        raise ValueError("Supply a separate Groq key, model and topic, or use manual scripts")
    from .config import Settings
    from .generation import HostedProvider
    # Settings(), unlike get_settings(), does not populate owner environment keys.
    settings = Settings(generation_provider="groq", groq_api_key=key, groq_model=model,
                        enable_hf_inference=False, max_provider_attempts_per_stage=1,
                        provider_max_retries=0, generation_diagnostics=False)
    provider = HostedProvider(settings, purpose="author")
    try:
        draft = provider.generate_json(
            "Write an original short Russian ILR 0+ everyday dialogue. Common words, factual details, no effects or acting cues. "
            "Use speaker IDs A and B. Two simple English comprehension questions, exactly four distinct choices A/B/C/D, "
            "correct key, English explanation and a short exact Russian evidence quotation. Orientation must not reveal answers.",
            topic[:2000], DialogueDraft, max_tokens=2600)
        item = materialize(draft, f"ru_draft_{uuid4().hex[:12]}", "groq", model)
        if key in item.model_dump_json():
            raise ValueError("Credential in text output")
        return item
    except Exception:
        raise ValueError("Text drafting failed. Check the separate Groq key/model/quota, or continue with manual scripts. No automatic retry.") from None
