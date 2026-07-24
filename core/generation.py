from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .audio import audio_duration_seconds, generate_cached_tts, validate_audio_file
from .config import Settings
from .constants import ILR_LEVELS, ILR_THETA, LETTERS, QUESTION_TYPES
from .item_bank import ItemBank, shuffle_question, shuffle_question_to_key
from .models import AudioAsset, GenerationMetadata, PassageItem, QuestionItem, ValidationReport, utc_now
from .prompts import (
    AUTHORING_SYSTEM,
    LEVEL_PROFILES,
    PROMPT_VERSION,
    VERIFIER_SYSTEM,
    blind_verification_prompt,
    blind_verification_batch_prompt,
    passage_audit_prompt,
    passage_authoring_prompt,
    passage_repair_prompt,
    question_authoring_prompt,
    question_repair_prompt,
)
from .storage import atomic_write_text
from .validation import answer_position_balance, content_hash, near_duplicate, normalize_text, validate_passage, validate_question


LOGGER = logging.getLogger("dlpt.genai")


class ProviderError(RuntimeError):
    pass


class GenerationValidationError(RuntimeError):
    pass


def _redact_error(value: object, settings: Settings | None = None, limit: int = 1000) -> str:
    text = str(value)
    if settings is not None:
        for secret in (settings.hf_token, settings.groq_api_key):
            if secret:
                text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(authorization|api[_ -]?key|token)([=: ]+)([^\s,;]+)", r"\1\2[REDACTED]", text)
    return text[:limit]


def _redact_payload(value: Any, settings: Settings | None = None) -> Any:
    """Recursively remove secret-bearing strings before logs or quarantine persistence."""
    if isinstance(value, dict):
        return {str(key): _redact_payload(item, settings) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_payload(item, settings) for item in value]
    if isinstance(value, tuple):
        return [_redact_payload(item, settings) for item in value]
    if isinstance(value, str):
        return _redact_error(value, settings, max(1000, len(value) + 32))
    return value


ILRLiteral = Literal["0", "0+", "1", "1+", "2", "2+", "3"]
QuestionTypeLiteral = Literal[
    "main idea",
    "prominent detail",
    "inference",
    "speaker/writer intent",
    "tone or attitude",
    "reference",
    "sequence",
    "cause and effect",
    "relationship of ideas",
    "meaning from context",
]


QUESTION_TYPE_ALIASES = {
    "main idea": "main idea",
    "main_idea": "main idea",
    "central idea": "main idea",
    "central message": "main idea",
    "gist": "main idea",
    "detail": "prominent detail",
    "specific detail": "prominent detail",
    "prominent detail": "prominent detail",
    "prominent_detail": "prominent detail",
    "key detail": "prominent detail",
    "inference": "inference",
    "inferencing": "inference",
    "implied meaning": "inference",
    "intent": "speaker/writer intent",
    "author intent": "speaker/writer intent",
    "writer intent": "speaker/writer intent",
    "speaker intent": "speaker/writer intent",
    "speaker/writer intent": "speaker/writer intent",
    "speaker or writer intent": "speaker/writer intent",
    "tone": "tone or attitude",
    "attitude": "tone or attitude",
    "tone/attitude": "tone or attitude",
    "tone or attitude": "tone or attitude",
    "reference": "reference",
    "referent": "reference",
    "pronoun reference": "reference",
    "sequence": "sequence",
    "chronology": "sequence",
    "order of events": "sequence",
    "cause and effect": "cause and effect",
    "cause/effect": "cause and effect",
    "causal relationship": "cause and effect",
    "relationship of ideas": "relationship of ideas",
    "relationship": "relationship of ideas",
    "idea relationship": "relationship of ideas",
    "organization of ideas": "relationship of ideas",
    "meaning from context": "meaning from context",
    "contextual meaning": "meaning from context",
    "vocabulary in context": "meaning from context",
    "word meaning in context": "meaning from context",
}


class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class CandidatePassageDraft(CandidateModel):
    orientation_en: str = Field(min_length=12, max_length=260)
    passage_ru: str = Field(min_length=3, max_length=12000)
    genre: str = Field(min_length=2, max_length=80)
    topic: str = Field(min_length=2, max_length=80)
    subtopic: str = Field(min_length=2, max_length=120)
    target_ilr: ILRLiteral
    register_name: str = Field(alias="register", serialization_alias="register", min_length=2, max_length=80)
    text_mode: str = Field(min_length=2, max_length=80)
    discourse_features: list[str] = Field(min_length=1, max_length=12)
    vocabulary_features: list[str] = Field(min_length=1, max_length=12)
    provisional_difficulty: float = Field(ge=-3.5, le=3.5)

    @field_validator("target_ilr")
    @classmethod
    def valid_ilr(cls, value: str) -> str:
        if value not in ILR_LEVELS:
            raise ValueError(f"target_ilr must be one of {ILR_LEVELS}")
        return value


# Backward-compatible import name used by the first hybrid release tests/extensions.
CandidatePassage = CandidatePassageDraft


def _canonical_question_type(value: Any) -> str:
    text = normalize_text(str(value or "")).replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text in QUESTION_TYPE_ALIASES:
        return QUESTION_TYPE_ALIASES[text]
    # Conservative keyword recovery for otherwise well-formed provider output.
    if "main" in text and ("idea" in text or "point" in text):
        return "main idea"
    if "detail" in text:
        return "prominent detail"
    if "infer" in text or "impli" in text:
        return "inference"
    if "intent" in text or "purpose" in text:
        return "speaker/writer intent"
    if "tone" in text or "attitude" in text:
        return "tone or attitude"
    if "refer" in text or "pronoun" in text:
        return "reference"
    if "sequence" in text or "chronolog" in text or "order" in text:
        return "sequence"
    if "cause" in text or "effect" in text or "result" in text:
        return "cause and effect"
    if "relationship" in text or "organization" in text or "structure" in text:
        return "relationship of ideas"
    if "context" in text or "vocab" in text or "word meaning" in text:
        return "meaning from context"
    return text


def _normalize_choices(value: Any) -> list[str]:
    if isinstance(value, dict):
        ordered: list[str] = []
        for key in ("A", "B", "C", "D", "a", "b", "c", "d", 0, 1, 2, 3, "0", "1", "2", "3"):
            if key in value and str(value[key]).strip():
                ordered.append(str(value[key]).strip())
        if len(ordered) == 4:
            return ordered
        return [str(item).strip() for item in value.values() if str(item).strip()]
    if isinstance(value, (list, tuple)):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("choice") or item.get("content") or item.get("value")
                if text is None and len(item) == 1:
                    text = next(iter(item.values()))
                normalized.append(str(text or "").strip())
            else:
                normalized.append(str(item).strip())
        return normalized
    return []


def _normalize_correct_index(value: Any, choices: list[str]) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if 0 <= value <= 3 else value - 1 if 1 <= value <= 4 else value
    if isinstance(value, float) and value.is_integer():
        return _normalize_correct_index(int(value), choices)
    text = str(value or "").strip()
    upper = text.upper().replace("OPTION", "").replace("CHOICE", "").strip(" :.-")
    if upper in LETTERS:
        return LETTERS.index(upper)
    if re.fullmatch(r"[0-4]", upper):
        number = int(upper)
        return number if 0 <= number <= 3 else number - 1
    normalized_text = normalize_text(text)
    for index, choice in enumerate(choices):
        if normalized_text and normalized_text == normalize_text(choice):
            return index
    return -1


class CandidateQuestion(CandidateModel):
    # Provider parsing only enforces shape and non-empty values. Quality limits
    # are enforced by deterministic validation, where failures can trigger one
    # targeted repair instead of eight blind provider retries.
    stem_en: str = Field(min_length=1, max_length=500)
    choices: list[str] = Field(min_length=4, max_length=4)
    proposed_correct_index: int = Field(ge=0, le=3)
    rationale_en: str = Field(min_length=1, max_length=1200)
    evidence_ru: str = Field(min_length=1, max_length=500)
    question_type: QuestionTypeLiteral

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        raw = dict(value)
        aliases = {
            "stem_en": ("stem_en", "stem", "question", "question_en", "prompt"),
            "choices": ("choices", "options", "answer_choices", "answers", "choices_en"),
            "proposed_correct_index": (
                "proposed_correct_index", "correct_index", "correct_answer_index", "answer_index",
                "correct_answer", "correct_choice", "answer",
            ),
            "rationale_en": ("rationale_en", "rationale", "explanation", "explanation_en", "reason"),
            "evidence_ru": ("evidence_ru", "evidence", "evidence_quote_ru", "quote_ru", "supporting_evidence"),
            "question_type": ("question_type", "type", "competency", "skill", "item_type"),
        }
        cleaned: dict[str, Any] = {}
        for canonical, names in aliases.items():
            for name in names:
                if name in raw and raw[name] is not None:
                    cleaned[canonical] = raw[name]
                    break
        choices = _normalize_choices(cleaned.get("choices"))
        cleaned["choices"] = choices
        cleaned["proposed_correct_index"] = _normalize_correct_index(
            cleaned.get("proposed_correct_index"), choices
        )
        cleaned["question_type"] = _canonical_question_type(cleaned.get("question_type"))
        return cleaned

    @field_validator("question_type")
    @classmethod
    def valid_question_type(cls, value: str) -> str:
        value = _canonical_question_type(value)
        if value not in QUESTION_TYPES:
            raise ValueError(f"Unsupported question_type: {value}")
        return value

class CandidateQuestionSet(CandidateModel):
    questions: list[CandidateQuestion] = Field(min_length=1, max_length=5)

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_envelope(cls, value: Any) -> Any:
        if isinstance(value, list):
            return {"questions": value}
        if not isinstance(value, dict):
            return value
        raw = dict(value)
        questions = raw.get("questions")
        if questions is None:
            for key in ("items", "question_set", "questions_en", "data", "results"):
                if key in raw:
                    questions = raw[key]
                    break
        if isinstance(questions, dict):
            nested = questions.get("questions") or questions.get("items")
            if nested is not None:
                questions = nested
            else:
                questions = list(questions.values())
        return {"questions": questions}


class PassageAudit(CandidateModel):
    acceptable: bool
    estimated_ilr: str
    confidence: float = Field(ge=0.0, le=1.0)
    natural_russian: bool
    coherent: bool
    orientation_safe: bool
    level_match: bool
    protected_content_risk: bool
    translation_artifacts: list[str]
    contradiction_flags: list[str]
    repetition_flags: list[str]
    repair_notes: list[str]

    @field_validator("estimated_ilr")
    @classmethod
    def valid_ilr(cls, value: str) -> str:
        if value not in ILR_LEVELS:
            raise ValueError(f"estimated_ilr must be one of {ILR_LEVELS}")
        return value


class BlindVerification(CandidateModel):
    selected_index: int = Field(ge=0, le=3)
    second_best_index: int = Field(ge=-1, le=3)
    confidence: float = Field(ge=0.0, le=1.0)
    multiple_plausible: bool
    requires_outside_knowledge: bool
    evidence_sufficient: bool
    reasoning_match: bool
    answer_leakage: bool
    evidence_quote_ru: str
    explanation: str


class BlindVerificationBatchItem(BlindVerification):
    question_index: int = Field(ge=0, le=4)


class BlindVerificationBatch(CandidateModel):
    verifications: list[BlindVerificationBatchItem] = Field(min_length=1, max_length=5)


@dataclass
class ProviderUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def start_call(self) -> None:
        """Count an outbound provider request, including failed structured-output attempts."""
        self.calls += 1

    def add_tokens(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        self.input_tokens += int(prompt_tokens or 0)
        self.output_tokens += int(completion_tokens or 0)

    def add(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        """Compatibility helper used by deterministic/custom providers."""
        self.start_call()
        self.add_tokens(prompt_tokens, completion_tokens)


class AuthoringProvider(ABC):
    last_provider: str = "unknown"
    last_model: str = "unknown"
    usage: ProviderUsage

    def __init__(self) -> None:
        self.usage = ProviderUsage()

    @abstractmethod
    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel: ...


class MockProvider(AuthoringProvider):
    """Deterministic development provider. It is never a silent production fallback."""

    last_provider = "mock"
    last_model = "deterministic-fixture-v4"

    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def _level(prompt: str) -> str:
        for pattern in (
            r"Requested provisional ILR target:\s*([^\n]+)",
            r"Provisional target ILR:\s*([^\n]+)",
            r"Target ILR:\s*([^\n]+)",
            r"TARGET_ILR=([^\n]+)",
        ):
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match and match.group(1).strip() in ILR_LEVELS:
                return match.group(1).strip()
        return "2"

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        self.usage.add(120, 80)
        level = self._level(prompt)
        if schema is CandidatePassageDraft or schema is CandidatePassage:
            skill = "listening" if "spoken transcript" in prompt or "Skill: listening" in prompt else "reading"
            passage = (
                "В городском культурном центре открылись вечерние курсы русского языка для взрослых. "
                "Программа рассчитана на жителей, которые уже знают основы языка, но хотят увереннее говорить на работе и в повседневной жизни. "
                "Занятия будут проходить по вторникам и четвергам с семи до восьми тридцати вечера. "
                "Организаторы сообщили, что в каждой группе будет не больше двенадцати человек, поэтому преподаватель сможет уделять внимание каждому участнику. "
                "Стоимость первого месяца снижена для тех, кто зарегистрируется заранее. "
                "Заявку необходимо отправить через сайт центра до пятницы, а подтверждение места придёт по электронной почте. "
                "Если желающих окажется больше, чем свободных мест, центр откроет дополнительную субботнюю группу."
            )
            return CandidatePassageDraft(
                orientation_en=f"You will {'hear' if skill == 'listening' else 'read'} a public announcement about an adult education program.",
                passage_ru=passage,
                genre="announcement",
                topic="education",
                subtopic="evening language courses",
                target_ilr=level,
                register_name="neutral public information",
                text_mode="spoken announcement" if skill == "listening" else "public announcement",
                discourse_features=["clear purpose", "schedule details", "conditional final detail"],
                vocabulary_features=["education vocabulary", "time expressions", "registration language"],
                provisional_difficulty=ILR_THETA.get(level, 0.5),
            )
        if schema is PassageAudit:
            return PassageAudit(
                acceptable=True,
                estimated_ilr=level,
                confidence=0.88,
                natural_russian=True,
                coherent=True,
                orientation_safe=True,
                level_match=True,
                protected_content_risk=False,
                translation_artifacts=[],
                contradiction_flags=[],
                repetition_flags=[],
                repair_notes=[],
            )
        if schema is CandidateQuestionSet:
            count_match = re.search(r"Create exactly (\d+)", prompt)
            count = int(count_match.group(1)) if count_match else 2
            candidates = [
                CandidateQuestion(
                    stem_en="What is the main purpose of the announcement?",
                    choices=[
                        "To announce evening Russian courses for adults",
                        "To cancel all programs at the cultural center",
                        "To advertise a new restaurant near the center",
                        "To report changes to public transportation",
                    ],
                    proposed_correct_index=0,
                    rationale_en="The announcement describes a new evening Russian course, its schedule, class size, price, and registration process.",
                    evidence_ru="открылись вечерние курсы русского языка для взрослых",
                    question_type="main idea",
                    target_ilr=level,
                    provisional_difficulty=ILR_THETA.get(level, 0.5),
                ),
                CandidateQuestion(
                    stem_en="When must an applicant submit the registration form?",
                    choices=["By Friday", "By Tuesday morning", "After the first month", "Only after receiving an email"],
                    proposed_correct_index=0,
                    rationale_en="The announcement explicitly says that the application must be sent through the center's website by Friday.",
                    evidence_ru="Заявку необходимо отправить через сайт центра до пятницы",
                    question_type="prominent detail",
                    target_ilr=level,
                    provisional_difficulty=ILR_THETA.get(level, 0.5) - 0.1,
                ),
                CandidateQuestion(
                    stem_en="What will the center do if demand exceeds the available places?",
                    choices=["Open an additional Saturday group", "Increase every class to twenty students", "Cancel the discounted price", "Move the course entirely online"],
                    proposed_correct_index=0,
                    rationale_en="The final sentence states that the center will open another Saturday group if there are more applicants than places.",
                    evidence_ru="центр откроет дополнительную субботнюю группу",
                    question_type="cause and effect",
                    target_ilr=level,
                    provisional_difficulty=ILR_THETA.get(level, 0.5) + 0.1,
                ),
                CandidateQuestion(
                    stem_en="Why does the announcement mention the class-size limit?",
                    choices=["It allows the teacher to give attention to each participant", "It guarantees that every student receives a job", "It permits the center to shorten every lesson", "It removes the need for advance registration"],
                    proposed_correct_index=0,
                    rationale_en="The class limit is linked directly to the teacher's ability to give attention to every participant.",
                    evidence_ru="преподаватель сможет уделять внимание каждому участнику",
                    question_type="cause and effect",
                    target_ilr=level,
                    provisional_difficulty=ILR_THETA.get(level, 0.5) + 0.1,
                ),
                CandidateQuestion(
                    stem_en="Which applicant receives the reduced first-month price?",
                    choices=["An applicant who registers early", "An applicant who attends only Saturdays", "An applicant who already works at the center", "An applicant who brings twelve classmates"],
                    proposed_correct_index=0,
                    rationale_en="The discount applies to people who register in advance.",
                    evidence_ru="для тех, кто зарегистрируется заранее",
                    question_type="reference",
                    target_ilr=level,
                    provisional_difficulty=ILR_THETA.get(level, 0.5),
                ),
            ]
            return CandidateQuestionSet(questions=candidates[:count])
        if schema in {BlindVerification, BlindVerificationBatch}:
            evidence_map = {
                "evening Russian courses": "открылись вечерние курсы русского языка для взрослых",
                "By Friday": "до пятницы",
                "additional Saturday group": "дополнительную субботнюю группу",
                "attention to each participant": "уделять внимание каждому участнику",
                "registers early": "зарегистрируется заранее",
            }

            def verify_choices(choices: list[str], question_index: int | None = None):
                selected = 0
                quote = ""
                for needle, evidence in evidence_map.items():
                    for index, choice in enumerate(choices):
                        if needle.casefold() in choice.casefold():
                            selected, quote = index, evidence
                            break
                    if quote:
                        break
                payload = dict(
                    selected_index=selected,
                    second_best_index=-1,
                    confidence=0.98,
                    multiple_plausible=False,
                    requires_outside_knowledge=False,
                    evidence_sufficient=True,
                    reasoning_match=True,
                    answer_leakage=False,
                    evidence_quote_ru=quote,
                    explanation="One choice is directly supported by the Russian source and the alternatives contradict or are absent from it.",
                )
                if question_index is None:
                    return BlindVerification(**payload)
                return BlindVerificationBatchItem(question_index=question_index, **payload)

            if schema is BlindVerification:
                choices_match = re.search(r"<CHOICES_ZERO_BASED>\s*(\[.*?\])\s*</CHOICES_ZERO_BASED>", prompt, re.S)
                choices = json.loads(choices_match.group(1)) if choices_match else []
                return verify_choices(choices)

            items_match = re.search(r"<ITEMS_JSON>\s*(\[.*?\])\s*</ITEMS_JSON>", prompt, re.S)
            items = json.loads(items_match.group(1)) if items_match else []
            return BlindVerificationBatch(
                verifications=[
                    verify_choices(list(item.get("choices", [])), int(item.get("question_index", index)))
                    for index, item in enumerate(items)
                ]
            )
        raise ProviderError(f"MockProvider does not support schema {schema.__name__}.")


class HostedProvider(AuthoringProvider):
    """Production provider adapter with fair failover and bounded compatibility modes.

    Provider-enforced JSON Schema is always attempted first. If a provider/model
    does not support it, the adapter can fall back to JSON-object mode and finally
    a controlled plain-JSON request. The parser accepts direct JSON or one complete
    fenced JSON document; it never extracts an arbitrary first ``{...}`` substring.
    """

    def __init__(self, settings: Settings, purpose: Literal["author", "verifier", "secondary_verifier"] = "author"):
        super().__init__()
        self.settings = settings
        self.purpose = purpose
        self._hf = None
        self._groq = None
        self.last_provider = "unknown"
        self.last_model = "unknown"
        self.last_mode = "unknown"
        self.last_errors: list[str] = []
        self._mode_cache: dict[tuple[str, str], str] = {}

    def _provider_order(self) -> list[str]:
        if self.purpose == "author":
            configured = self.settings._author_provider_order()
        else:
            configured = self.settings.verifier_provider_order()
            if self.purpose == "secondary_verifier":
                configured = list(reversed(configured))
        return [
            name for name in configured
            if (name == "hf" and self.settings.hf_token) or (name == "groq" and self.settings.groq_api_key)
        ]

    def _model_for(self, provider: str) -> str:
        if provider == "hf":
            return self.settings.hf_text_model if self.purpose == "author" else self.settings.hf_verifier_model
        return self.settings.groq_model if self.purpose == "author" else self.settings.groq_verifier_model

    @staticmethod
    def _usage_from_response(response: Any) -> tuple[int | None, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None, None
        prompt = getattr(usage, "prompt_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
        return prompt, completion

    @staticmethod
    def _response_text(response: Any) -> str:
        try:
            message = response.choices[0].message
        except Exception as exc:
            raise ProviderError("Provider returned no usable assistant message.") from exc
        parsed = getattr(message, "parsed", None)
        if parsed is not None:
            if isinstance(parsed, BaseModel):
                return parsed.model_dump_json()
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    chunks.append(str(item.get("text") or item.get("content") or ""))
                else:
                    chunks.append(str(getattr(item, "text", "")))
            return "".join(chunks)
        return str(content or "")

    @staticmethod
    def _validation_summary(exc: Exception, limit: int = 6) -> str:
        if not isinstance(exc, ValidationError):
            return type(exc).__name__
        parts: list[str] = []
        for error in exc.errors(include_url=False, include_input=False)[:limit]:
            location = ".".join(str(part) for part in error.get("loc", ())) or "root"
            message = str(error.get("msg", "validation failed"))
            parts.append(f"{location}: {message}")
        remaining = max(0, len(exc.errors()) - len(parts))
        if remaining:
            parts.append(f"+{remaining} more")
        return "; ".join(parts)

    @classmethod
    def _parse_structured_text(cls, text: str, schema: type[BaseModel]) -> BaseModel:
        cleaned = (text or "").strip().lstrip("\ufeff")
        if not cleaned:
            raise ProviderError("Provider returned an empty structured response.")
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.I | re.S)
        if fenced:
            cleaned = fenced.group(1).strip()
        try:
            payload = json.loads(cleaned)
        except Exception as exc:
            raise ProviderError(
                f"Provider returned invalid JSON for {schema.__name__}: {type(exc).__name__}."
            ) from exc
        try:
            # model_validate, rather than model_validate_json, deliberately runs
            # provider-compatibility normalizers before strict field validation.
            return schema.model_validate(payload)
        except ValidationError as exc:
            shape = type(payload).__name__
            if isinstance(payload, dict):
                shape += f" keys={sorted(str(key) for key in payload)[:10]}"
            raise ProviderError(
                f"Provider response did not match {schema.__name__}: "
                f"{cls._validation_summary(exc)} (payload {shape})."
            ) from exc

    def _call_hf(
        self,
        system: str,
        prompt: str,
        *,
        model: str,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        from huggingface_hub import InferenceClient

        if not self.settings.hf_token:
            raise ProviderError("Hugging Face generation was selected but HF_TOKEN is unavailable.")
        if self._hf is None:
            try:
                self._hf = InferenceClient(
                    provider=self.settings.hf_provider,
                    token=self.settings.hf_token,
                    timeout=self.settings.provider_timeout_seconds,
                )
            except TypeError:
                self._hf = InferenceClient(token=self.settings.hf_token, timeout=self.settings.provider_timeout_seconds)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        self.usage.start_call()
        response = self._hf.chat.completions.create(**kwargs)
        prompt_tokens, completion_tokens = self._usage_from_response(response)
        self.usage.add_tokens(prompt_tokens, completion_tokens)
        return self._response_text(response)

    def _call_groq(
        self,
        system: str,
        prompt: str,
        *,
        model: str,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        from groq import Groq

        if not self.settings.groq_api_key:
            raise ProviderError("Groq generation was selected but GROQ_API_KEY is unavailable.")
        if self._groq is None:
            self._groq = Groq(api_key=self.settings.groq_api_key, timeout=self.settings.provider_timeout_seconds)
        common: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": 0.9,
        }
        if response_format is not None:
            common["response_format"] = response_format
        # GPT-OSS reasoning is useful but medium/high effort adds avoidable latency to
        # assessment authoring. Older Groq SDKs ignore this via the TypeError fallback.
        if model.startswith("openai/gpt-oss"):
            common["reasoning_effort"] = "low"
        self.usage.start_call()
        try:
            response = self._groq.chat.completions.create(max_completion_tokens=max_tokens, **common)
        except TypeError:
            common.pop("reasoning_effort", None)
            try:
                response = self._groq.chat.completions.create(max_completion_tokens=max_tokens, **common)
            except TypeError:
                response = self._groq.chat.completions.create(max_tokens=max_tokens, **common)
        prompt_tokens, completion_tokens = self._usage_from_response(response)
        self.usage.add_tokens(prompt_tokens, completion_tokens)
        return self._response_text(response)

    def _response_modes(self, provider: str, model: str) -> list[str]:
        configured = self.settings.structured_output_mode
        if configured == "strict":
            modes = ["strict"]
        elif configured == "best_effort":
            modes = ["best_effort", "json_object"]
        elif configured == "json_object":
            modes = ["json_object"]
        else:
            modes = ["strict", "best_effort", "json_object"]
        if self.settings.allow_plain_json_fallback and configured != "strict":
            modes.append("plain_json")
        cached = self._mode_cache.get((provider, model))
        if cached in modes:
            modes = [cached] + [mode for mode in modes if mode != cached]
        return modes

    @staticmethod
    def _response_format(schema: type[BaseModel], mode: str) -> dict[str, Any] | None:
        if mode == "plain_json":
            return None
        if mode == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": re.sub(r"[^A-Za-z0-9_-]", "_", schema.__name__)[:64],
                "description": f"Structured output for {schema.__name__}",
                "schema": schema.model_json_schema(by_alias=True),
                "strict": mode == "strict",
            },
        }

    @staticmethod
    def _schema_instruction(schema: type[BaseModel]) -> str:
        return (
            "\n\nReturn exactly one JSON document matching this JSON Schema. "
            "Do not use markdown fences or add prose:\n"
            + json.dumps(schema.model_json_schema(by_alias=True), ensure_ascii=False)
        )

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        text = str(exc)
        lower = text.lower()
        if "401" in lower or "unauthorized" in lower:
            return "authentication failed; verify the secret value"
        if "403" in lower or "forbidden" in lower:
            return "token lacks Inference Providers permission or provider access"
        if "402" in lower or "payment required" in lower or "credits" in lower:
            return "provider credits/quota are unavailable"
        if "429" in lower or "rate limit" in lower:
            return "provider rate limit reached"
        if "404" in lower or "not found" in lower:
            return "configured model/provider route was not found"
        if "timeout" in lower or "timed out" in lower:
            return "provider request timed out"
        return _redact_error(exc, None, 220)

    def _attempt_plan(self, order: list[str]) -> list[tuple[str, str, str]]:
        """Round-robin output modes across providers instead of exhausting one provider first."""
        provider_modes = {
            provider: self._response_modes(provider, self._model_for(provider)) for provider in order
        }
        max_modes = max((len(modes) for modes in provider_modes.values()), default=0)
        plan: list[tuple[str, str, str]] = []
        for mode_index in range(max_modes):
            for provider in order:
                modes = provider_modes[provider]
                if mode_index < len(modes):
                    plan.append((provider, self._model_for(provider), modes[mode_index]))
        return plan

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        order = self._provider_order()
        if not order:
            if self.settings.generation_provider == "disabled":
                raise ProviderError("Live generation is disabled; validated bank content remains available.")
            raise ProviderError(
                "No configured live provider is ready. Add an HF_TOKEN with Inference Providers permission and/or GROQ_API_KEY."
            )
        max_tokens = int(max_tokens or 3200)
        temperature = float(
            self.settings.authoring_temperature if temperature is None and self.purpose == "author"
            else self.settings.verification_temperature if temperature is None
            else temperature
        )
        errors: list[str] = []
        stage_attempts = 0
        attempt_cap = self.settings.max_provider_attempts_per_stage
        exhausted = False
        plan = self._attempt_plan(order)
        for retry in range(self.settings.provider_max_retries + 1):
            for provider, model, mode in plan:
                if stage_attempts >= attempt_cap:
                    exhausted = True
                    break
                stage_attempts += 1
                self.last_provider = "huggingface" if provider == "hf" else provider
                self.last_model = model
                self.last_mode = mode
                response_format = self._response_format(schema, mode)
                request_prompt = prompt
                if mode in {"json_object", "plain_json"}:
                    request_prompt += self._schema_instruction(schema)
                if self.settings.generation_diagnostics:
                    LOGGER.info(
                        "GenAI request purpose=%s schema=%s provider=%s model=%s mode=%s attempt=%s/%s",
                        self.purpose, schema.__name__, provider, model, mode, stage_attempts, attempt_cap,
                    )
                try:
                    text = (
                        self._call_hf(
                            system,
                            request_prompt,
                            model=model,
                            response_format=response_format,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        if provider == "hf"
                        else self._call_groq(
                            system,
                            request_prompt,
                            model=model,
                            response_format=response_format,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                    )
                    parsed = self._parse_structured_text(text, schema)
                    self._mode_cache[(provider, model)] = mode
                    self.last_errors = errors[-8:]
                    if self.settings.generation_diagnostics:
                        LOGGER.info(
                            "GenAI success purpose=%s schema=%s provider=%s model=%s mode=%s",
                            self.purpose, schema.__name__, provider, model, mode,
                        )
                    return parsed
                except Exception as exc:
                    safe = self._friendly_error(exc)
                    entry = f"{provider}/{model}/{mode}:{type(exc).__name__}:{safe}"
                    errors.append(entry)
                    if self.settings.generation_diagnostics:
                        LOGGER.warning(
                            "GenAI attempt failed purpose=%s schema=%s provider=%s model=%s mode=%s reason=%s",
                            self.purpose, schema.__name__, provider, model, mode, safe,
                        )
            if exhausted:
                break
            if retry < self.settings.provider_max_retries:
                time.sleep(min(8.0, (2 ** retry) + random.random()))
        self.last_errors = errors[-8:]
        suffix = f" Stage request cap ({attempt_cap}) reached." if exhausted else ""
        detail = " | ".join(errors[-8:])
        raise ProviderError(
            "All configured providers failed to return valid structured content."
            + suffix
            + (" " + detail if detail else "")
        )


QUESTION_DIFFICULTY_OFFSETS = {
    "prominent detail": -0.15,
    "sequence": -0.10,
    "reference": -0.05,
    "main idea": 0.0,
    "meaning from context": 0.05,
    "cause and effect": 0.10,
    "relationship of ideas": 0.15,
    "speaker/writer intent": 0.20,
    "tone or attitude": 0.20,
    "inference": 0.25,
}

HIGH_RISK_TYPES = {"inference", "speaker/writer intent", "tone or attitude", "relationship of ideas", "meaning from context"}

PASSAGE_TOKEN_GUIDANCE = {
    "0": 1400, "0+": 1500, "1": 1700, "1+": 2100,
    "2": 2500, "2+": 3000, "3": 3600,
}


def _stage_token_budget(
    configured_cap: int,
    *,
    stage: str,
    level: str,
    skill: str,
    question_count: int = 1,
) -> int:
    """Use the configured value as a hard cap while avoiding oversized low-level calls."""
    if stage == "passage":
        guidance = PASSAGE_TOKEN_GUIDANCE[level]
        if skill == "listening":
            guidance = int(guidance * 0.90)
    elif stage == "questions":
        guidance = 900 + 520 * max(1, question_count)
    elif stage == "audit":
        guidance = 1200 if level in {"2+", "3"} else 900
    elif stage == "verifier":
        per_item = 360 if level in {"2+", "3"} else 300
        guidance = 450 + per_item * max(1, question_count)
    else:  # repair
        guidance = max(PASSAGE_TOKEN_GUIDANCE[level], 1000 + 520 * max(1, question_count))
    return max(250, min(int(configured_cap), int(guidance)))


def _should_audit_passage(settings: Settings, *, mode: str, skill: str, level: str) -> bool:
    if settings.generation_audit_mode == "off":
        return False
    if settings.generation_audit_mode == "always":
        return True
    # Smart mode retains full auditing for strict conditions and higher-risk content,
    # while allowing low-level Reading Training authoring to save one provider call.
    return mode in {"diagnostic", "simulation"} or skill == "listening" or level in {"2+", "3"}


def _safe_guidance(values: list[str] | None, fallback: str) -> list[str]:
    cleaned: list[str] = []
    for value in (values or [])[:8]:
        value = re.sub(r"[^A-Za-zА-Яа-яЁё0-9 +&/'-]", "", value).strip()[:60]
        if value:
            cleaned.append(value)
    return cleaned or [fallback]


def _provisional_question_difficulty(level: str, question_type: str, model_value: float | None = None) -> float:
    base = ILR_THETA.get(level, ILR_THETA["2"]) + QUESTION_DIFFICULTY_OFFSETS.get(question_type, 0.0)
    if model_value is not None:
        base = 0.8 * base + 0.2 * max(base - 0.6, min(base + 0.6, model_value))
    return max(-3.5, min(3.5, base))


def _provisional_passage_difficulty(level: str, model_value: float) -> float:
    base = ILR_THETA.get(level, ILR_THETA["2"])
    bounded_model = max(base - 0.5, min(base + 0.5, model_value))
    return max(-3.5, min(3.5, 0.8 * base + 0.2 * bounded_model))


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)?", text))


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?…])\s+", text.strip()) if item.strip()]


def _cyrillic_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        return 0.0
    return sum(bool(re.match(r"[А-Яа-яЁё]", char)) for char in letters) / len(letters)


def _repeated_ngram(text: str, n: int = 9) -> bool:
    words = normalize_text(text).split()
    if len(words) < n * 2:
        return False
    grams = [tuple(words[index:index + n]) for index in range(len(words) - n + 1)]
    return len(set(grams)) < len(grams)


def _soft_range(level: str, skill: str) -> tuple[int, int]:
    raw = LEVEL_PROFILES[level].soft_reading_words if skill == "reading" else LEVEL_PROFILES[level].soft_listening_words
    low, high = raw.split("-")
    return int(low), int(high)


def validate_candidate_passage(candidate: CandidatePassageDraft, *, skill: str, requested_level: str) -> list[str]:
    issues: list[str] = []
    text = candidate.passage_ru.strip()
    words = _word_count(text)
    sentences = _sentences(text)
    low, high = _soft_range(requested_level, skill)
    if candidate.target_ilr != requested_level:
        issues.append("candidate_target_level_does_not_match_request")
    if _cyrillic_ratio(text) < 0.72:
        issues.append("passage_is_not_predominantly_russian")
    if words < max(3, math.floor(low * 0.55)):
        issues.append("passage_is_far_below_level_appropriate_discourse_length")
    if skill == "reading" and words > 500:
        issues.append("reading_passage_exceeds_500_word_hard_limit")
    if skill == "listening" and words > max(360, math.ceil(high * 1.15)):
        issues.append("listening_transcript_likely_exceeds_2_5_minute_limit")
    normalized_sentences = [normalize_text(item) for item in sentences if len(normalize_text(item).split()) >= 5]
    if len(normalized_sentences) != len(set(normalized_sentences)):
        issues.append("repeated_sentence_detected")
    if _repeated_ngram(text):
        issues.append("repeated_phrase_or_padding_detected")
    if any(len(normalize_text(sentence).split()) > 55 for sentence in sentences):
        issues.append("unreasonably_long_sentence_detected")
    if skill == "listening" and any(len(normalize_text(sentence).split()) > 42 for sentence in sentences):
        issues.append("listening_sentence_too_long_for_natural_tts")
    if re.search(r"[<>{}\[\]|]", text):
        issues.append("tts_or_markup_breaking_characters_detected")
    if re.search(r"(?i)\b(dlpt|dliflc|department of defense|dod)\b", text):
        issues.append("protected_test_or_affiliation_reference_detected")
    if len(candidate.discourse_features) < 1 or len(candidate.vocabulary_features) < 1:
        issues.append("missing_observable_complexity_metadata")
    if requested_level in {"2+", "3"} and len(sentences) < 5:
        issues.append("upper_level_passage_lacks_sufficient_discourse_development")
    if requested_level == "3" and skill == "reading" and text.count("\n") < 1 and len(sentences) < 8:
        issues.append("ilr3_reading_lacks_cross_part_structure")
    return sorted(set(issues))


def _desired_question_count(skill: str, maximum: int, word_count: int, mode: str) -> int:
    maximum = max(1, min(maximum, 5 if skill == "reading" else 3))
    if skill == "reading":
        suggested = 1 if word_count < 90 else 2 if word_count < 220 else 3 if word_count < 340 else 4 if word_count < 430 else 5
    else:
        suggested = 1 if word_count < 75 else 2 if word_count < 170 else 3
    if mode == "simulation" and maximum > 1:
        suggested = max(2, suggested)
    return max(1, min(maximum, suggested))


def _novelty_context(bank: ItemBank, skill: str, limit: int = 12) -> list[str]:
    items = [
        f"{passage.genre}: {passage.topic} / {passage.subtopic}"
        for passage in bank.active_passages(skill)
    ]
    return items[-limit:]


def _candidate_passage_json(candidate: CandidatePassageDraft) -> str:
    return candidate.model_dump_json(indent=2, by_alias=True)


def _candidate_questions_json(candidate: CandidateQuestionSet) -> str:
    return candidate.model_dump_json(indent=2)


def _provider_generate(
    provider: AuthoringProvider,
    system: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    max_tokens: int,
    temperature: float,
) -> BaseModel:
    try:
        return provider.generate_json(
            system,
            prompt,
            schema,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except TypeError as exc:
        # Compatibility with a user-supplied provider implementing the v1.1 three-argument interface.
        if "unexpected keyword" not in str(exc) and "positional" not in str(exc):
            raise
        return provider.generate_json(system, prompt, schema)


def materialize_candidate(
    candidate: CandidatePassageDraft,
    question_set: CandidateQuestionSet | str,
    passage_id: str | None = None,
    skill: str | None = None,
    requested_level: str | None = None,
    generation_metadata: GenerationMetadata | None = None,
    shuffle: bool = False,
) -> tuple[PassageItem, list[QuestionItem]]:
    """Convert typed candidates into bank models.

    v1.1 called this with (combined_candidate, passage_id, skill). v1.2 uses separate passage and
    question stages. The compatibility branch accepts the old positional shape only when a custom
    CandidatePassage-like object exposes a ``questions`` attribute.
    """
    if isinstance(question_set, str):
        # Compatibility for old extensions: materialize_candidate(candidate_with_questions, passage_id, skill, ...)
        old_passage_id = question_set
        old_skill = passage_id
        raw_questions = getattr(candidate, "questions", None)
        if raw_questions is None or not isinstance(old_skill, str):
            raise TypeError("v1.2 materialize_candidate requires a CandidateQuestionSet")
        question_set = CandidateQuestionSet(questions=raw_questions)
        passage_id = old_passage_id
        skill = old_skill
    if not isinstance(question_set, CandidateQuestionSet):
        raise TypeError("question_set must be CandidateQuestionSet")
    if passage_id is None or skill is None:
        raise TypeError("passage_id and skill are required")
    level = requested_level or candidate.target_ilr
    question_ids = [f"{passage_id}_q{i + 1}" for i in range(len(question_set.questions))]
    generation_metadata = generation_metadata or GenerationMetadata(
        provider="hosted", model="configured", prompt_version=PROMPT_VERSION, pipeline_version=PROMPT_VERSION
    )
    passage = PassageItem(
        id=passage_id,
        skill=skill,
        target_ilr=level,
        provisional_difficulty=_provisional_passage_difficulty(level, candidate.provisional_difficulty),
        genre=candidate.genre.strip().lower()[:80] or "general",
        topic=candidate.topic.strip().lower()[:80] or "general",
        subtopic=candidate.subtopic.strip().lower()[:120] or "general",
        orientation_en=candidate.orientation_en.strip(),
        passage_ru=candidate.passage_ru.strip(),
        source_type="synthetic",
        word_count=_word_count(candidate.passage_ru),
        segment_count=max(1, len([part for part in re.split(r"\n\s*\n|(?<=[.!?…])\s+", candidate.passage_ru) if part.strip()])),
        vocabulary_metadata={
            "features": candidate.vocabulary_features,
            "provisional_ilr": level,
        },
        discourse_metadata={
            "register": candidate.register_name,
            "text_mode": candidate.text_mode,
            "features": candidate.discourse_features,
            "complexity_basis": "discourse and reasoning demand, not length alone",
        },
        question_ids=question_ids,
        content_hash=content_hash(candidate.passage_ru),
        duplicate_detection_hash=content_hash(normalize_text(candidate.passage_ru)),
        generation=generation_metadata,
        provenance={
            "authoring_method": "live structured generation",
            "requested_mode": "user-session",
            "source_type": "synthetic",
        },
    )
    questions: list[QuestionItem] = []
    for index, raw in enumerate(question_set.questions):
        choices = {letter: raw.choices[i].strip() for i, letter in enumerate(LETTERS)}
        q_type = raw.question_type.strip().lower()
        question = QuestionItem(
            id=question_ids[index],
            passage_id=passage_id,
            stem_en=raw.stem_en.strip(),
            choices=choices,
            correct_key=LETTERS[raw.proposed_correct_index],
            rationale_en=raw.rationale_en.strip(),
            evidence_ru=raw.evidence_ru.strip(),
            question_type=q_type,
            target_ilr=level,
            # The LLM does not assign operational item difficulty. Difficulty is
            # derived deterministically from the requested ILR and question type.
            provisional_difficulty=_provisional_question_difficulty(level, q_type, None),
            generation=generation_metadata,
        )
        questions.append(shuffle_question(question) if shuffle else question)
    return passage, questions


def validate_candidate_questions(
    question_set: CandidateQuestionSet,
    passage: PassageItem,
    questions: list[QuestionItem],
    *,
    desired_count: int,
    requested_level: str,
) -> list[str]:
    issues: list[str] = []
    if len(question_set.questions) != desired_count:
        issues.append(f"question_count_must_be_exactly_{desired_count}")
    seen_stems: list[str] = []
    seen_evidence: list[str] = []
    detail_count = 0
    for index, question in enumerate(questions, start=1):
        report = validate_question(question, passage)
        issues.extend(f"q{index}:{reason}" for reason in report.failure_reasons + report.ambiguity_flags)
        if question.target_ilr != requested_level:
            issues.append(f"q{index}:target_level_mismatch")
        if question.question_type == "prominent detail":
            detail_count += 1
        stem_norm = normalize_text(question.stem_en)
        if any(near_duplicate(stem_norm, prior, 0.82) for prior in seen_stems):
            issues.append(f"q{index}:near_duplicate_stem")
        seen_stems.append(stem_norm)
        evidence_norm = normalize_text(question.evidence_ru)
        if evidence_norm in seen_evidence and len(questions) > 1:
            issues.append(f"q{index}:duplicate_evidence_span")
        seen_evidence.append(evidence_norm)
        if normalize_text(question.rationale_en) == evidence_norm:
            issues.append(f"q{index}:rationale_duplicates_evidence")
        if requested_level in {"0", "0+"} and question.question_type not in {"prominent detail", "main idea"}:
            issues.append(f"q{index}:question_type_too_complex_for_low_level")
        if requested_level == "3" and question.question_type == "prominent detail" and detail_count > 1:
            issues.append(f"q{index}:too_many_isolated_detail_questions_for_ilr3")
    return sorted(set(issues))


def _level_distance(a: str, b: str) -> int:
    return abs(ILR_LEVELS.index(a) - ILR_LEVELS.index(b))


def _meaningful_audit_flags(values: list[str]) -> list[str]:
    benign = {"", "none", "no", "n/a", "not detected", "no issues", "no issue", "нет", "не обнаружено"}
    return [value.strip() for value in values if value.strip().casefold() not in benign]


def _audit_issues(audit: PassageAudit, requested_level: str) -> list[str]:
    issues: list[str] = []
    if not audit.acceptable:
        issues.append("independent_passage_audit_rejected")
    if not audit.natural_russian:
        issues.append("independent_audit_detected_unnatural_russian")
    if not audit.coherent:
        issues.append("independent_audit_detected_incoherence")
    if not audit.orientation_safe:
        issues.append("independent_audit_detected_orientation_leak")
    if audit.protected_content_risk:
        issues.append("independent_audit_detected_protected_content_risk")
    if not audit.level_match or _level_distance(audit.estimated_ilr, requested_level) > 1:
        issues.append(f"independent_audit_level_mismatch_{audit.estimated_ilr}")
    issues.extend(f"translation_artifact:{item}" for item in _meaningful_audit_flags(audit.translation_artifacts))
    issues.extend(f"contradiction:{item}" for item in _meaningful_audit_flags(audit.contradiction_flags))
    issues.extend(f"repetition:{item}" for item in _meaningful_audit_flags(audit.repetition_flags))
    return sorted(set(issues))


def validate_with_blind_verifier(
    provider: AuthoringProvider,
    passage: PassageItem,
    question: QuestionItem,
    *,
    max_tokens: int = 900,
    temperature: float = 0.0,
    seed_suffix: str = "primary",
) -> ValidationReport:
    original = [(letter, question.choices[letter]) for letter in LETTERS]
    rng = random.Random(f"{question.id}:{seed_suffix}")
    shuffled = original.copy()
    rng.shuffle(shuffled)
    choices = [text for _, text in shuffled]
    verification = _provider_generate(
        provider,
        VERIFIER_SYSTEM,
        blind_verification_prompt(
            passage_ru=passage.passage_ru,
            stem_en=question.stem_en,
            choices=choices,
            target_level=question.target_ilr,
            question_type=question.question_type,
        ),
        BlindVerification,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    verification = BlindVerification.model_validate(verification)
    selected_key = shuffled[verification.selected_index][0]
    second_key = shuffled[verification.second_best_index][0] if verification.second_best_index >= 0 else None
    deterministic = validate_question(question, passage)
    failures = list(deterministic.failure_reasons)
    flags = list(deterministic.ambiguity_flags)
    if selected_key != question.correct_key:
        failures.append("blind_verifier_disagreed")
    if verification.multiple_plausible:
        failures.append("multiple_plausible_answers")
    if verification.requires_outside_knowledge:
        failures.append("requires_outside_knowledge")
    if not verification.evidence_sufficient:
        failures.append("insufficient_evidence")
    if not verification.reasoning_match:
        failures.append("reasoning_level_mismatch")
    if verification.answer_leakage:
        failures.append("answer_choice_leakage")
    if verification.confidence < 0.60:
        flags.append("low_verifier_confidence")
    if verification.evidence_quote_ru and normalize_text(verification.evidence_quote_ru) not in normalize_text(passage.passage_ru):
        failures.append("verifier_evidence_not_in_passage")
    return ValidationReport(
        status="accepted" if not failures and not flags else "rejected",
        deterministic_checks=deterministic.deterministic_checks,
        validator_scores={
            "blind_agreement": 1.0 if selected_key == question.correct_key else 0.0,
            "blind_confidence": verification.confidence,
        },
        ambiguity_flags=flags,
        failure_reasons=sorted(set(failures)),
        blind_verifier_answer=selected_key,
        proposed_answer=question.correct_key,
    )



def validate_with_blind_verifier_batch(
    provider: AuthoringProvider,
    passage: PassageItem,
    questions: list[QuestionItem],
    *,
    max_tokens: int = 1800,
    temperature: float = 0.0,
    seed_suffix: str = "primary",
) -> list[ValidationReport]:
    """Blind-verify a complete passage bundle in one provider call.

    The proposed keys are never included. Each question receives a separate,
    deterministic shuffled order, and the returned indices are mapped back only
    after the independent provider has answered.
    """
    if not questions:
        return []
    prepared: list[tuple[QuestionItem, list[tuple[str, str]]]] = []
    items: list[dict[str, Any]] = []
    for question_index, question in enumerate(questions):
        shuffled = [(letter, question.choices[letter]) for letter in LETTERS]
        random.Random(f"{question.id}:{seed_suffix}").shuffle(shuffled)
        prepared.append((question, shuffled))
        items.append({
            "question_index": question_index,
            "target_ilr": question.target_ilr,
            "question_type": question.question_type,
            "stem_en": question.stem_en,
            "choices": [text for _, text in shuffled],
        })

    try:
        raw = _provider_generate(
            provider,
            VERIFIER_SYSTEM,
            blind_verification_batch_prompt(passage_ru=passage.passage_ru, items=items),
            BlindVerificationBatch,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        batch = BlindVerificationBatch.model_validate(raw)
    except ProviderError as exc:
        # Backward compatibility for user-supplied v1.1 providers that only
        # implemented the single-question verifier schema.
        if "does not support schema BlindVerificationBatch" not in str(exc):
            raise
        return [
            validate_with_blind_verifier(
                provider,
                passage,
                question,
                max_tokens=max(600, max_tokens // max(1, len(questions))),
                temperature=temperature,
                seed_suffix=seed_suffix,
            )
            for question in questions
        ]

    by_index: dict[int, BlindVerificationBatchItem] = {}
    for verification in batch.verifications:
        if verification.question_index in by_index:
            raise GenerationValidationError("Blind verifier returned a duplicate question_index.")
        by_index[verification.question_index] = verification
    expected = set(range(len(questions)))
    if set(by_index) != expected:
        raise GenerationValidationError("Blind verifier did not return exactly one result for every question.")

    reports: list[ValidationReport] = []
    for question_index, (question, shuffled) in enumerate(prepared):
        verification = by_index[question_index]
        selected_key = shuffled[verification.selected_index][0]
        deterministic = validate_question(question, passage)
        failures = list(deterministic.failure_reasons)
        flags = list(deterministic.ambiguity_flags)
        if selected_key != question.correct_key:
            failures.append("blind_verifier_disagreed")
        if verification.multiple_plausible:
            failures.append("multiple_plausible_answers")
        if verification.requires_outside_knowledge:
            failures.append("requires_outside_knowledge")
        if not verification.evidence_sufficient:
            failures.append("insufficient_evidence")
        if not verification.reasoning_match:
            failures.append("reasoning_level_mismatch")
        if verification.answer_leakage:
            failures.append("answer_choice_leakage")
        if verification.confidence < 0.60:
            flags.append("low_verifier_confidence")
        if (
            verification.evidence_quote_ru
            and normalize_text(verification.evidence_quote_ru) not in normalize_text(passage.passage_ru)
        ):
            failures.append("verifier_evidence_not_in_passage")
        reports.append(ValidationReport(
            status="accepted" if not failures and not flags else "rejected",
            deterministic_checks=deterministic.deterministic_checks,
            validator_scores={
                "blind_agreement": 1.0 if selected_key == question.correct_key else 0.0,
                "blind_confidence": verification.confidence,
                "batched_verification": 1.0,
            },
            ambiguity_flags=sorted(set(flags)),
            failure_reasons=sorted(set(failures)),
            blind_verifier_answer=selected_key,
            proposed_answer=question.correct_key,
        ))
    return reports


@dataclass
class GeneratedBundle:
    passage: PassageItem
    questions: list[QuestionItem]
    passage_report: ValidationReport
    question_reports: list[ValidationReport]
    audio_asset: AudioAsset | None
    provider_name: str
    model_name: str
    verifier_provider: str | None = None
    verifier_model: str | None = None
    request_count: int = 0
    repair_count: int = 0
    bank_persistence_note: str = ""
    bank_remote_synced: bool = False
    generated_bank_passage_count: int = 0
    generated_bank_question_count: int = 0


@dataclass
class PipelineTrace:
    stages: list[dict[str, Any]] = field(default_factory=list)
    repair_count: int = 0

    def add(self, stage: str, status: str, **details: Any) -> None:
        self.stages.append({"stage": stage, "status": status, **details})


class LiveGenerationService:
    def __init__(
        self,
        settings: Settings,
        bank: ItemBank,
        project_root: str | Path,
        provider: AuthoringProvider | None = None,
        verifier_provider: AuthoringProvider | None = None,
        secondary_verifier_provider: AuthoringProvider | None = None,
    ):
        self.settings = settings
        self.bank = bank
        self.project_root = Path(project_root)
        self.provider = provider or (MockProvider() if settings.generation_provider == "mock" else HostedProvider(settings, "author"))
        if verifier_provider is not None:
            self.verifier_provider = verifier_provider
        elif provider is not None:
            self.verifier_provider = provider
        else:
            self.verifier_provider = MockProvider() if settings.generation_provider == "mock" else HostedProvider(settings, "verifier")
        if secondary_verifier_provider is not None:
            self.secondary_verifier_provider = secondary_verifier_provider
        elif provider is not None:
            self.secondary_verifier_provider = provider
        else:
            self.secondary_verifier_provider = MockProvider() if settings.generation_provider == "mock" else HostedProvider(settings, "secondary_verifier")
        self._semaphore = threading.BoundedSemaphore(settings.generation_concurrency_limit)
        self._quarantine_lock = threading.RLock()

    def _quarantine(self, payload: dict[str, Any]) -> None:
        path = self.settings.quarantine_runtime_path(self.project_root) / "live_generation_failures.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_payload = _redact_payload(payload, self.settings)
        record = {"recorded_at": utc_now().isoformat(), "pipeline_version": PROMPT_VERSION, **safe_payload}
        with self._quarantine_lock:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            atomic_write_text(path, existing + json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _build_audio(self, passage: PassageItem) -> tuple[PassageItem, AudioAsset]:
        cache_dir = self.settings.audio_cache_runtime_path(self.project_root)
        path = generate_cached_tts(
            passage.passage_ru,
            cache_dir,
            voice=self.settings.edge_tts_voice,
            rate=self.settings.edge_tts_rate,
            engine_version="edge-tts-7.2.8",
        )
        if not validate_audio_file(path):
            raise GenerationValidationError("Generated listening audio was missing or incomplete.")
        duration = audio_duration_seconds(path)
        if duration is not None and not 3 <= duration <= 165:
            raise GenerationValidationError(f"Generated listening audio duration was outside the operational range: {duration:.1f}s")
        audio_id = f"aud_{uuid4().hex[:16]}"
        asset = AudioAsset(
            id=audio_id,
            path=str(path),
            content_hash=content_hash(passage.passage_ru),
            voice=self.settings.edge_tts_voice,
            rate=self.settings.edge_tts_rate,
            engine="edge-tts",
            engine_version="7.2.8",
            duration_seconds=duration,
            transcript_hash=content_hash(passage.passage_ru),
            synthetic_tts=True,
            validated=True,
        )
        updated = passage.model_copy(update={
            "audio_asset_id": audio_id,
            "audio_duration_seconds": duration,
            "voice_metadata": {
                "voice": self.settings.edge_tts_voice,
                "rate": self.settings.edge_tts_rate,
                "engine": "edge-tts",
                "engine_version": "7.2.8",
                "synthetic": True,
            },
        })
        return updated, asset

    @staticmethod
    def _provider_usage(provider: AuthoringProvider) -> ProviderUsage:
        return getattr(provider, "usage", ProviderUsage())

    def _total_usage(self) -> ProviderUsage:
        usage = ProviderUsage()
        unique: dict[int, AuthoringProvider] = {
            id(self.provider): self.provider,
            id(self.verifier_provider): self.verifier_provider,
            id(self.secondary_verifier_provider): self.secondary_verifier_provider,
        }
        for provider in unique.values():
            current = self._provider_usage(provider)
            usage.calls += current.calls
            usage.input_tokens += current.input_tokens
            usage.output_tokens += current.output_tokens
        return usage

    def _generate_passage(
        self,
        *,
        skill: str,
        level: str,
        mode: str,
        topics: list[str],
        competencies: list[str],
        trace: PipelineTrace,
    ) -> tuple[CandidatePassageDraft, PassageAudit | None]:
        nonce = uuid4().hex[:12]
        prompt = passage_authoring_prompt(
            skill=skill,
            mode=mode,
            level=level,
            topics=topics,
            competencies=competencies,
            novelty_context=_novelty_context(self.bank, skill),
            generation_nonce=nonce,
        )
        candidate = CandidatePassageDraft.model_validate(_provider_generate(
            self.provider,
            AUTHORING_SYSTEM,
            prompt,
            CandidatePassageDraft,
            max_tokens=_stage_token_budget(
                self.settings.passage_max_tokens, stage="passage", level=level, skill=skill
            ),
            temperature=self.settings.authoring_temperature,
        ))
        trace.add("passage_generation", "received", word_count=_word_count(candidate.passage_ru))

        audit: PassageAudit | None = None
        for attempt in range(self.settings.generation_repair_attempts + 1):
            issues = validate_candidate_passage(candidate, skill=skill, requested_level=level)
            audit_required = _should_audit_passage(
                self.settings, mode=mode, skill=skill, level=level
            )
            if not issues and audit_required:
                audit = PassageAudit.model_validate(_provider_generate(
                    self.verifier_provider,
                    VERIFIER_SYSTEM,
                    passage_audit_prompt(skill=skill, requested_level=level, candidate_json=_candidate_passage_json(candidate)),
                    PassageAudit,
                    max_tokens=_stage_token_budget(
                        self.settings.audit_max_tokens, stage="audit", level=level, skill=skill
                    ),
                    temperature=self.settings.verification_temperature,
                ))
                issues.extend(_audit_issues(audit, level))
            elif not issues:
                trace.add("passage_audit", "skipped", policy=self.settings.generation_audit_mode)
            if not issues:
                trace.add("passage_validation", "accepted", audit=audit.model_dump(mode="json") if audit else None)
                return candidate, audit
            trace.add("passage_validation", "rejected", attempt=attempt, issues=issues)
            if attempt >= self.settings.generation_repair_attempts:
                raise GenerationValidationError("Generated passage failed validation: " + ", ".join(issues[:12]))
            candidate = CandidatePassageDraft.model_validate(_provider_generate(
                self.provider,
                AUTHORING_SYSTEM,
                passage_repair_prompt(
                    skill=skill,
                    level=level,
                    issues=issues + (audit.repair_notes if audit else []),
                    candidate_json=_candidate_passage_json(candidate),
                ),
                CandidatePassageDraft,
                max_tokens=_stage_token_budget(
                    self.settings.repair_max_tokens, stage="repair", level=level, skill=skill
                ),
                temperature=max(0.05, self.settings.authoring_temperature - 0.05),
            ))
            trace.repair_count += 1
            audit = None
        raise GenerationValidationError("Passage generation ended unexpectedly.")

    def _generate_questions(
        self,
        *,
        candidate_passage: CandidatePassageDraft,
        passage_id: str,
        skill: str,
        level: str,
        mode: str,
        competencies: list[str],
        maximum_questions: int,
        metadata: GenerationMetadata,
        trace: PipelineTrace,
    ) -> tuple[PassageItem, list[QuestionItem], ValidationReport, list[ValidationReport]]:
        desired_count = _desired_question_count(skill, maximum_questions, _word_count(candidate_passage.passage_ru), mode)
        passage_json = _candidate_passage_json(candidate_passage)
        question_set = CandidateQuestionSet.model_validate(_provider_generate(
            self.provider,
            AUTHORING_SYSTEM,
            question_authoring_prompt(
                skill=skill,
                mode=mode,
                level=level,
                desired_count=desired_count,
                competencies=competencies,
                passage_json=passage_json,
            ),
            CandidateQuestionSet,
            max_tokens=_stage_token_budget(
                self.settings.question_max_tokens, stage="questions", level=level, skill=skill,
                question_count=desired_count,
            ),
            temperature=min(self.settings.authoring_temperature, 0.15),
        ))
        trace.add("question_generation", "received", count=len(question_set.questions), desired_count=desired_count)

        last_issues: list[str] = []
        for attempt in range(self.settings.generation_repair_attempts + 1):
            passage, questions = materialize_candidate(
                candidate_passage,
                question_set,
                passage_id,
                skill,
                requested_level=level,
                generation_metadata=metadata,
                shuffle=False,
            )
            issues = validate_candidate_questions(
                question_set,
                passage,
                questions,
                desired_count=desired_count,
                requested_level=level,
            )
            primary_reports: list[ValidationReport] = []
            secondary_reports: list[ValidationReport | None] = [None for _ in questions]
            if not issues:
                primary_reports = validate_with_blind_verifier_batch(
                    self.verifier_provider,
                    passage,
                    questions,
                    max_tokens=_stage_token_budget(
                        self.settings.verifier_max_tokens, stage="verifier", level=level, skill=skill,
                        question_count=len(questions),
                    ),
                    temperature=self.settings.verification_temperature,
                    seed_suffix="primary",
                )
                for index, primary in enumerate(primary_reports, start=1):
                    issues.extend(f"q{index}:{item}" for item in primary.failure_reasons + primary.ambiguity_flags)

                high_risk_indices = [
                    index for index, (question, primary) in enumerate(zip(questions, primary_reports))
                    if (
                        self.settings.second_verifier_high_risk
                        and level in {"2+", "3"}
                        and question.question_type in HIGH_RISK_TYPES
                        and primary.status == "accepted"
                    )
                ]
                if high_risk_indices:
                    high_risk_questions = [questions[index] for index in high_risk_indices]
                    secondary_batch = validate_with_blind_verifier_batch(
                        self.secondary_verifier_provider,
                        passage,
                        high_risk_questions,
                        max_tokens=_stage_token_budget(
                            self.settings.verifier_max_tokens, stage="verifier", level=level, skill=skill,
                            question_count=len(high_risk_questions),
                        ),
                        temperature=self.settings.verification_temperature,
                        seed_suffix="secondary",
                    )
                    for original_index, second in zip(high_risk_indices, secondary_batch):
                        secondary_reports[original_index] = second
                        issues.extend(
                            f"q{original_index + 1}:secondary:{item}"
                            for item in second.failure_reasons + second.ambiguity_flags
                        )
            if not issues:
                passage_report = validate_passage(passage, questions)
                if passage_report.status != "accepted":
                    issues.extend(passage_report.failure_reasons)
                else:
                    merged_reports: list[ValidationReport] = []
                    for primary, secondary in zip(primary_reports, secondary_reports):
                        scores = dict(primary.validator_scores)
                        if secondary is not None:
                            scores.update({f"secondary_{key}": value for key, value in secondary.validator_scores.items()})
                        merged_reports.append(primary.model_copy(update={"validator_scores": scores}))
                    trace.add("question_validation", "accepted", count=len(questions))
                    return passage, questions, passage_report, merged_reports
            last_issues = sorted(set(issues))
            trace.add("question_validation", "rejected", attempt=attempt, issues=last_issues)
            if attempt >= self.settings.generation_repair_attempts:
                raise GenerationValidationError("Generated questions failed validation: " + ", ".join(last_issues[:16]))
            question_set = CandidateQuestionSet.model_validate(_provider_generate(
                self.provider,
                AUTHORING_SYSTEM,
                question_repair_prompt(
                    skill=skill,
                    level=level,
                    desired_count=desired_count,
                    passage_json=passage_json,
                    questions_json=_candidate_questions_json(question_set),
                    issues=last_issues,
                ),
                CandidateQuestionSet,
                max_tokens=_stage_token_budget(
                    self.settings.repair_max_tokens, stage="repair", level=level, skill=skill,
                    question_count=desired_count,
                ),
                temperature=min(0.10, max(0.0, self.settings.authoring_temperature - 0.10)),
            ))
            trace.repair_count += 1
        raise GenerationValidationError("Question generation ended unexpectedly: " + ", ".join(last_issues))

    def generate_and_store(
        self,
        *,
        skill: str,
        level: str,
        mode: str,
        topics: list[str] | None,
        competencies: list[str] | None,
        maximum_questions: int,
    ) -> GeneratedBundle:
        ready, message = self.settings.provider_readiness()
        if not ready:
            raise ProviderError(message)
        if skill not in {"reading", "listening"}:
            raise ValueError("skill must be reading or listening")
        if level not in ILR_LEVELS:
            raise ValueError(f"level must be one of {ILR_LEVELS}")
        maximum = max(1, min(maximum_questions, 5 if skill == "reading" else 3))
        clean_topics = _safe_guidance(topics, "balanced real-world topics")
        clean_competencies = [item for item in _safe_guidance(competencies, "balanced comprehension competencies") if item in QUESTION_TYPES]
        if not clean_competencies:
            clean_competencies = []
        acquired = self._semaphore.acquire(timeout=self.settings.provider_timeout_seconds + 5)
        if not acquired:
            raise ProviderError("The live-generation queue is busy; bank fallback should be used.")
        candidate: CandidatePassageDraft | None = None
        trace = PipelineTrace()
        usage_before = self._total_usage()
        try:
            candidate, audit = self._generate_passage(
                skill=skill,
                level=level,
                mode=mode,
                topics=clean_topics,
                competencies=clean_competencies,
                trace=trace,
            )
            passage_id = f"gen_{uuid4().hex[:16]}"
            # Metadata is finalized after all calls; initial object is copied into items and replaced before persistence.
            metadata = GenerationMetadata(
                provider=self.provider.last_provider,
                model=self.provider.last_model,
                prompt_version=PROMPT_VERSION,
                pipeline_version=PROMPT_VERSION,
                verifier_provider=getattr(self.verifier_provider, "last_provider", None),
                verifier_model=getattr(self.verifier_provider, "last_model", None),
                authoring_notes=f"Requested skill={skill}, mode={mode}, ILR={level}. Difficulty remains provisional.",
            )
            passage, unshuffled_questions, passage_report, blind_reports = self._generate_questions(
                candidate_passage=candidate,
                passage_id=passage_id,
                skill=skill,
                level=level,
                mode=mode,
                competencies=clean_competencies,
                maximum_questions=maximum,
                metadata=metadata,
                trace=trace,
            )
            duplicate = self.bank.duplicate_of(passage)
            if duplicate:
                raise GenerationValidationError(f"Generated passage duplicated existing bank item {duplicate}.")

            rng = random.Random(passage_id)
            bank_counts = answer_position_balance(self.bank.questions.values())
            shuffled_questions: list[QuestionItem] = []
            for question in unshuffled_questions:
                minimum = min(bank_counts.values()) if bank_counts else 0
                least_used = [letter for letter in LETTERS if bank_counts.get(letter, 0) == minimum]
                target_key = rng.choice(least_used)
                shuffled = shuffle_question_to_key(question, target_key, rng)
                shuffled_questions.append(shuffled)
                bank_counts[target_key] = bank_counts.get(target_key, 0) + 1

            final_reports: list[ValidationReport] = []
            accepted_questions: list[QuestionItem] = []
            for question, blind_report in zip(shuffled_questions, blind_reports):
                final_check = validate_question(question, passage)
                if final_check.status != "accepted":
                    raise GenerationValidationError("A question failed validation after code-side answer shuffling.")
                report = ValidationReport(
                    status="accepted",
                    deterministic_checks=final_check.deterministic_checks,
                    validator_scores=blind_report.validator_scores,
                    blind_verifier_answer=question.correct_key,
                    proposed_answer=question.correct_key,
                )
                final_reports.append(report)
                accepted_questions.append(question.model_copy(update={
                    "validation_report_id": report.id,
                    "validation_status": "accepted",
                    "status": "active",
                }))

            usage_after = self._total_usage()
            request_count = max(0, usage_after.calls - usage_before.calls)
            input_tokens = max(0, usage_after.input_tokens - usage_before.input_tokens)
            output_tokens = max(0, usage_after.output_tokens - usage_before.output_tokens)
            final_metadata = metadata.model_copy(update={
                "provider": self.provider.last_provider,
                "model": self.provider.last_model,
                "verifier_provider": getattr(self.verifier_provider, "last_provider", None),
                "verifier_model": getattr(self.verifier_provider, "last_model", None),
                "secondary_verifier_provider": getattr(self.secondary_verifier_provider, "last_provider", None),
                "secondary_verifier_model": getattr(self.secondary_verifier_provider, "last_model", None),
                "request_count": request_count,
                "repair_count": trace.repair_count,
                "input_tokens": input_tokens or None,
                "output_tokens": output_tokens or None,
                "authoring_notes": (
                    f"Requested skill={skill}, mode={mode}, ILR={level}; "
                    f"audit_estimate={audit.estimated_ilr if audit else 'not_run'}; difficulty remains provisional."
                ),
            })
            passage = passage.model_copy(update={
                "generation": final_metadata,
                "validation_report_id": passage_report.id,
                "validation_status": "accepted",
                "status": "active",
                "question_ids": [question.id for question in accepted_questions],
            })
            accepted_questions = [question.model_copy(update={"generation": final_metadata}) for question in accepted_questions]
            audio_asset = None
            if skill == "listening":
                passage, audio_asset = self._build_audio(passage)

            commit_result = self.bank.append_validated_bundle(
                passage,
                accepted_questions,
                passage_report,
                final_reports,
                audio_asset,
            )
            commit_note = getattr(commit_result, "note", "") if commit_result is not None else ""
            remote_synced = bool(getattr(commit_result, "remote_synced", False)) if commit_result is not None else False
            generated_passages = int(getattr(commit_result, "passage_count", 0)) if commit_result is not None else 0
            generated_questions = int(getattr(commit_result, "question_count", 0)) if commit_result is not None else 0
            return GeneratedBundle(
                passage=passage,
                questions=accepted_questions,
                passage_report=passage_report,
                question_reports=final_reports,
                audio_asset=audio_asset,
                provider_name=final_metadata.provider,
                model_name=final_metadata.model,
                verifier_provider=final_metadata.verifier_provider,
                verifier_model=final_metadata.verifier_model,
                request_count=request_count,
                repair_count=trace.repair_count,
                bank_persistence_note=commit_note,
                bank_remote_synced=remote_synced,
                generated_bank_passage_count=generated_passages,
                generated_bank_question_count=generated_questions,
            )
        except Exception as exc:
            usage_after = self._total_usage()
            failed_request_count = max(0, usage_after.calls - usage_before.calls)
            failed_input_tokens = max(0, usage_after.input_tokens - usage_before.input_tokens)
            failed_output_tokens = max(0, usage_after.output_tokens - usage_before.output_tokens)
            try:
                setattr(exc, "request_count", failed_request_count)
                setattr(exc, "repair_count", trace.repair_count)
            except Exception:
                pass
            try:
                self._quarantine({
                    "skill": skill,
                    "level": level,
                    "mode": mode,
                    "provider": getattr(self.provider, "last_provider", "unknown"),
                    "model": getattr(self.provider, "last_model", "unknown"),
                    "verifier_provider": getattr(self.verifier_provider, "last_provider", "unknown"),
                    "verifier_model": getattr(self.verifier_provider, "last_model", "unknown"),
                    "error_type": type(exc).__name__,
                    "error": _redact_error(exc, self.settings, 1000),
                    "candidate": candidate.model_dump(mode="json") if candidate is not None else None,
                    "trace": trace.stages,
                    "repair_count": trace.repair_count,
                    "request_count": failed_request_count,
                    "input_tokens": failed_input_tokens or None,
                    "output_tokens": failed_output_tokens or None,
                })
            except Exception:
                pass
            raise
        finally:
            self._semaphore.release()
