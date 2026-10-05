from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from .constants import ILR_LEVELS, LETTERS, QUESTION_TYPES
from .languages import SUPPORTED_LANGUAGE_CODES


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class GenerationMetadata(StrictModel):
    provider: str = "manual"
    model: str = "human-authored"
    model_revision: str | None = None
    prompt_version: str = "starter-bank-v1"
    pipeline_version: str | None = None
    verifier_provider: str | None = None
    verifier_model: str | None = None
    secondary_verifier_provider: str | None = None
    secondary_verifier_model: str | None = None
    request_count: int = 0
    repair_count: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    authoring_notes: str | None = None


class ValidationReport(StrictModel):
    id: str = Field(default_factory=lambda: f"vr_{uuid4().hex}")
    status: Literal["accepted", "rejected", "needs_review"]
    deterministic_checks: dict[str, bool] = Field(default_factory=dict)
    validator_scores: dict[str, float] = Field(default_factory=dict)
    ambiguity_flags: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    blind_verifier_answer: str | None = None
    proposed_answer: str | None = None
    reviewed_at: datetime = Field(default_factory=utc_now)


class AudioAsset(StrictModel):
    id: str
    source_type: Literal["authentic/open-licensed", "transformed/adapted", "synthetic"] = "synthetic"
    path: str | None = None
    url: str | None = None
    content_hash: str
    voice: str | None = None
    rate: str | None = None
    engine: str | None = None
    engine_version: str | None = None
    duration_seconds: float | None = None
    transcript_hash: str
    license: str = "Project-authored synthetic content"
    synthetic_tts: bool = True
    validated: bool = False


class ItemStatistics(StrictModel):
    exposure_count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    distractor_counts: dict[str, int] = Field(default_factory=dict)
    item_total_correlation: float | None = None
    passage_effect: float | None = None
    discrimination: float | None = None
    calibrated_difficulty: float | None = None
    calibration_sample_size: int = 0
    mode_counts: dict[str, int] = Field(default_factory=dict)
    retired_reason: str | None = None
    last_exposed_at: datetime | None = None


class QuestionItem(StrictModel):
    id: str
    passage_id: str
    stem_en: str
    choices: dict[str, str]
    correct_key: str
    rationale_en: str
    evidence_ru: str
    question_type: str
    target_ilr: str
    provisional_difficulty: float
    calibrated_difficulty: float | None = None
    discrimination: float = 1.0
    validator_scores: dict[str, float] = Field(default_factory=dict)
    ambiguity_flags: list[str] = Field(default_factory=list)
    answer_position_metadata: dict[str, Any] = Field(default_factory=dict)
    distractor_quality: dict[str, float] = Field(default_factory=dict)
    generation: GenerationMetadata = Field(default_factory=GenerationMetadata)
    validation_status: Literal["accepted", "rejected", "needs_review"] = "accepted"
    validation_report_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    status: Literal["active", "quarantined", "retired"] = "active"
    statistics: ItemStatistics = Field(default_factory=ItemStatistics)

    @field_validator("correct_key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        value = value.upper()
        if value not in LETTERS:
            raise ValueError("correct_key must be A, B, C, or D")
        return value

    @field_validator("target_ilr")
    @classmethod
    def valid_ilr(cls, value: str) -> str:
        if value not in ILR_LEVELS:
            raise ValueError(f"target_ilr must be one of {ILR_LEVELS}")
        return value

    @field_validator("question_type")
    @classmethod
    def valid_question_type(cls, value: str) -> str:
        if value not in QUESTION_TYPES:
            raise ValueError(f"Unsupported question_type: {value}")
        return value

    @model_validator(mode="after")
    def validate_choices(self):
        if set(self.choices) != set(LETTERS):
            raise ValueError("choices must contain exactly A, B, C, and D")
        normalized = [v.strip().casefold() for v in self.choices.values()]
        if any(not value for value in normalized) or len(set(normalized)) != 4:
            raise ValueError("choices must be non-empty and unique")
        return self

    @property
    def operational_difficulty(self) -> float:
        return self.calibrated_difficulty if self.calibrated_difficulty is not None else self.provisional_difficulty


class PassageItem(StrictModel):
    id: str
    language: str = "ru"
    skill: Literal["reading", "listening"]
    target_ilr: str
    provisional_difficulty: float
    calibrated_difficulty: float | None = None
    genre: str
    topic: str
    subtopic: str
    orientation_en: str
    passage_ru: str
    source_type: Literal["authentic/open-licensed", "transformed/adapted", "synthetic"] = "synthetic"
    provenance: dict[str, str] = Field(default_factory=dict)
    license: str = "Project-authored synthetic content"
    word_count: int
    audio_duration_seconds: float | None = None
    segment_count: int = 1
    vocabulary_metadata: dict[str, Any] = Field(default_factory=dict)
    discourse_metadata: dict[str, Any] = Field(default_factory=dict)
    question_ids: list[str]
    audio_asset_id: str | None = None
    voice_metadata: dict[str, Any] = Field(default_factory=dict)
    generation: GenerationMetadata = Field(default_factory=GenerationMetadata)
    validation_status: Literal["accepted", "rejected", "needs_review"] = "accepted"
    validation_report_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    exposure_count: int = 0
    status: Literal["active", "quarantined", "retired"] = "active"
    content_hash: str
    duplicate_detection_hash: str

    @field_validator("target_ilr")
    @classmethod
    def valid_ilr(cls, value: str) -> str:
        if value not in ILR_LEVELS:
            raise ValueError(f"target_ilr must be one of {ILR_LEVELS}")
        return value

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGE_CODES:
            raise ValueError(f"language must be one of {SUPPORTED_LANGUAGE_CODES}")
        return value

    @model_validator(mode="after")
    def validate_bundle_size(self):
        count = len(self.question_ids)
        if self.skill == "reading" and not 1 <= count <= 5:
            raise ValueError("Reading passages must contain 1–5 questions")
        if self.skill == "listening" and not 1 <= count <= 3:
            raise ValueError("Listening passages must contain 1–3 questions")
        if not self.orientation_en.strip() or not self.passage_ru.strip():
            raise ValueError("orientation_en and passage_ru are required")
        return self

    @property
    def operational_difficulty(self) -> float:
        return self.calibrated_difficulty if self.calibrated_difficulty is not None else self.provisional_difficulty


class AbilityEstimate(StrictModel):
    skill: Literal["reading", "listening"]
    theta: float = 0.0
    standard_error: float = 1.25
    ci_low: float = -2.5
    ci_high: float = 2.5
    posterior_grid: list[float] = Field(default_factory=list)
    posterior_weights: list[float] = Field(default_factory=list)
    items_answered: int = 0
    correct: int = 0
    practice_ilr: str | None = None
    confidence: Literal["insufficient", "low", "moderate", "high"] = "insufficient"
    provisional: bool = True
    stable: bool = False
    predicted_success: dict[str, float] = Field(default_factory=dict)
    routing_ilr: str = "1+"
    routing_history: list[dict[str, Any]] = Field(default_factory=list)
    evidence_by_ilr: dict[str, int] = Field(default_factory=dict)
    correct_by_ilr: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("routing_ilr")
    @classmethod
    def validate_routing_ilr(cls, value: str) -> str:
        if value not in ILR_LEVELS:
            raise ValueError(f"routing_ilr must be one of {ILR_LEVELS}")
        return value


class AdaptiveSelection(StrictModel):
    passage_id: str
    skill: Literal["reading", "listening"]
    score: float
    information: float
    ability_distance: float
    target_bias: float = 0.0
    balance_penalty: float = 0.0
    exposure_penalty: float = 0.0
    routing_band: str | None = None
    selected_band: str | None = None
    band_distance: int = 0
    reasons: list[str] = Field(default_factory=list)


class ResponseRecord(StrictModel):
    session_id: str
    passage_id: str
    question_id: str
    skill: Literal["reading", "listening"]
    mode: Literal["training", "diagnostic", "simulation", "assessment"]
    language: str = "ru"
    target_ilr: str
    item_difficulty: float
    item_discrimination: float = Field(default=1.0, gt=0.0, le=3.0)
    question_type: str
    topic: str
    genre: str
    stem_en: str
    choices_snapshot: dict[str, str]
    rationale_en: str
    evidence_ru: str
    selected_key: str | None
    correct_key: str
    is_correct: bool
    response_time_seconds: float
    listening_play_count: int = 0
    answer_change_count: int = 0
    provisional_item: bool = True
    submitted_at: datetime = Field(default_factory=utc_now)


class SessionCheckpoint(StrictModel):
    session_id: str
    version: int = 1
    saved_at: datetime = Field(default_factory=utc_now)
    checksum: str
    session_payload: dict[str, Any]


class UserHistory(StrictModel):
    profile_id: str
    language: str = "ru"
    seen_passage_ids: list[str] = Field(default_factory=list)
    seen_question_ids: list[str] = Field(default_factory=list)
    reading_estimates: list[dict[str, Any]] = Field(default_factory=list)
    listening_estimates: list[dict[str, Any]] = Field(default_factory=list)
    response_records: list[ResponseRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionState(StrictModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    profile_id: str | None = None
    language: str = "ru"
    mode: Literal["training", "diagnostic", "simulation", "assessment"]
    selected_skills: list[Literal["reading", "listening"]]
    active_skill_index: int = 0
    start_level: str = "1+"
    target_level: str = "2"
    adaptive_start_policy: Literal["medium", "selected"] = "medium"
    minimum_ilr: str = "0"
    maximum_ilr: str = "3"
    topics: list[str] = Field(default_factory=list)
    competencies: list[str] = Field(default_factory=list)
    max_questions_per_skill: int = 16
    minimum_questions_per_skill: int = 8
    assessment_min_passages: int = Field(default=6, ge=2, le=40)
    assessment_max_passages: int = Field(default=18, ge=2, le=40)
    assessment_target_sd: float = Field(default=0.55, ge=0.3, le=0.8)
    assessment_end_reasons: dict[str, str] = Field(default_factory=dict)
    simulation_full: bool = False
    shortened_simulation: bool = False
    timer_mode: Literal["off", "standard", "strict"] = "off"
    time_limit_seconds_per_skill: int | None = None
    skill_started_at_epoch: float | None = None
    skill_deadline_epoch: float | None = None
    session_started_at_epoch: float
    current_passage_id: str | None = None
    current_question_ids: list[str] = Field(default_factory=list)
    current_started_at_epoch: float | None = None
    current_answers: dict[str, str] = Field(default_factory=dict)
    current_answer_changes: dict[str, int] = Field(default_factory=dict)
    # Final-selection timestamps are captured independently for each visible
    # question. Older checkpoints load safely because this field has a default.
    current_answer_timestamps: dict[str, float] = Field(default_factory=dict)
    current_listening_plays: int = 0
    demo_mode: bool = False
    current_listening_completed: int = 0
    completed_passage_ids: list[str] = Field(default_factory=list)
    completed_question_ids: list[str] = Field(default_factory=list)
    responses: list[ResponseRecord] = Field(default_factory=list)
    reading_ability: AbilityEstimate
    listening_ability: AbilityEstimate
    topic_exposure: dict[str, int] = Field(default_factory=dict)
    genre_exposure: dict[str, int] = Field(default_factory=dict)
    question_type_exposure: dict[str, int] = Field(default_factory=dict)
    item_exposure: dict[str, int] = Field(default_factory=dict)
    status: Literal["active", "completed", "stopped", "expired", "error"] = "active"
    checkpoint_path: str | None = None
    last_error: str | None = None
    feedback_mode: Literal["immediate", "end_of_passage", "end_only"] = "end_only"
    hints_enabled: bool = False
    transcript_review_enabled: bool = False
    replay_allowed: bool = False
    slow_audio_allowed: bool = False
    voice_label: str = "Starter-bank Russian voice"
    speech_rate_label: str = "Normal"
    content_source: Literal["bank_only", "fresh_ai_preferred"] = "bank_only"
    generation_requests: int = 0
    generation_api_calls: int = 0
    generation_repair_count: int = 0
    generated_passage_ids: list[str] = Field(default_factory=list)
    generation_failures: int = 0
    bank_fallback_count: int = 0
    last_content_source: Literal["starter_bank", "generated_bank", "fresh_ai"] | None = None
    last_content_note: str | None = None
    request_nonce: str | None = None
    handled_nonces: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adaptive_band_range(self):
        if self.assessment_min_passages > self.assessment_max_passages:
            raise ValueError("Minimum assessment passages cannot exceed maximum passages")
        if self.language not in SUPPORTED_LANGUAGE_CODES:
            raise ValueError(f"language must be one of {SUPPORTED_LANGUAGE_CODES}")
        if self.minimum_ilr not in ILR_LEVELS or self.maximum_ilr not in ILR_LEVELS:
            raise ValueError("minimum_ilr and maximum_ilr must be valid ILR bands")
        if ILR_LEVELS.index(self.minimum_ilr) > ILR_LEVELS.index(self.maximum_ilr):
            raise ValueError("minimum_ilr cannot be higher than maximum_ilr")
        return self

    @property
    def active_skill(self) -> str:
        return self.selected_skills[self.active_skill_index]

    def ability_for(self, skill: str) -> AbilityEstimate:
        return self.reading_ability if skill == "reading" else self.listening_ability

    def responses_for(self, skill: str) -> list[ResponseRecord]:
        return [record for record in self.responses if record.skill == skill]

    def completed_count(self, skill: str | None = None) -> int:
        target = skill or self.active_skill
        return len(self.responses_for(target))
