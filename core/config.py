from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()


class Settings(BaseModel):
    app_name: str = "Russian Adaptive Proficiency Practice"
    environment: str = "production"
    data_dir: Path = Path("data")
    storage_dir: Path = Path("storage")
    item_bank_path: Path = Path("data/starter_items.jsonl")
    generated_item_bank_path: Path = Path("storage/item_bank/generated_items.jsonl")
    audio_cache_dir: Path = Path("storage/cache/audio")
    session_dir: Path = Path("storage/sessions")
    history_dir: Path = Path("storage/history")
    quarantine_dir: Path = Path("storage/quarantine")
    persistent_storage_path: Path | None = None
    storage_backend: str = "local"
    hf_dataset_repo: str | None = None

    # Secrets are read only from environment/Space secrets. They are never serialized into app data.
    hf_token: str | None = Field(default=None, exclude=True, repr=False)
    groq_api_key: str | None = Field(default=None, exclude=True, repr=False)

    # Hybrid authoring/provider configuration.
    generation_provider: str = "hf_then_groq"
    verification_provider: str = "auto"
    enable_user_generation: bool = True
    hf_provider: str = "auto"
    hf_text_model: str = "openai/gpt-oss-120b"
    hf_verifier_model: str = "openai/gpt-oss-20b"
    groq_model: str = "openai/gpt-oss-120b"
    groq_verifier_model: str = "openai/gpt-oss-20b"
    structured_output_mode: str = "auto"
    provider_timeout_seconds: int = Field(default=45, ge=5, le=180)
    provider_max_retries: int = Field(default=2, ge=0, le=6)
    max_provider_attempts_per_stage: int = Field(default=4, ge=1, le=12)
    generation_concurrency_limit: int = Field(default=1, ge=1, le=4)
    queue_concurrency_limit: int = Field(default=4, ge=1, le=16)
    max_generation_requests_per_session: int = Field(default=8, ge=0, le=40)
    generation_repair_attempts: int = Field(default=1, ge=0, le=3)
    generation_audit_mode: str = "always"
    second_verifier_high_risk: bool = True
    authoring_temperature: float = Field(default=0.25, ge=0.0, le=1.5)
    verification_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    passage_max_tokens: int = Field(default=3200, ge=500, le=12000)
    question_max_tokens: int = Field(default=2600, ge=500, le=10000)
    repair_max_tokens: int = Field(default=3200, ge=500, le=12000)
    audit_max_tokens: int = Field(default=1200, ge=300, le=5000)
    verifier_max_tokens: int = Field(default=900, ge=250, le=4000)

    enable_history: bool = True
    enable_analytics: bool = False
    checkpoint_after_passage: bool = True
    audio_cache_max_age_days: int = Field(default=30, ge=1, le=365)
    orphan_temp_max_age_hours: int = Field(default=12, ge=1, le=168)
    edge_tts_voice: str = "ru-RU-SvetlanaNeural"
    edge_tts_rate: str = "+0%"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=7860, ge=1, le=65535)

    @field_validator("generation_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {"disabled", "huggingface", "groq", "hf_then_groq", "groq_then_hf", "mock"}
        value = value.strip().lower()
        aliases = {"hf": "huggingface", "hf_only": "huggingface", "groq_only": "groq"}
        value = aliases.get(value, value)
        if value not in allowed:
            raise ValueError(f"GENERATION_PROVIDER/GENAI_PROVIDER must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("verification_provider")
    @classmethod
    def validate_verifier_provider(cls, value: str) -> str:
        allowed = {"auto", "huggingface", "groq", "hf_then_groq", "groq_then_hf", "mock"}
        value = value.strip().lower()
        aliases = {"hf": "huggingface", "hf_only": "huggingface", "groq_only": "groq"}
        value = aliases.get(value, value)
        if value not in allowed:
            raise ValueError(f"VERIFICATION_PROVIDER must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("structured_output_mode")
    @classmethod
    def validate_structured_mode(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"auto", "strict", "best_effort", "json_object"}
        if value not in allowed:
            raise ValueError(f"STRUCTURED_OUTPUT_MODE must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("generation_audit_mode")
    @classmethod
    def validate_audit_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"always", "smart", "off"}:
            raise ValueError("GENERATION_AUDIT_MODE must be always, smart, or off")
        return value

    @property
    def effective_storage_dir(self) -> Path:
        return self.persistent_storage_path or self.storage_dir

    def runtime_path(self, configured: Path, project_root: Path, persistent_relative: str | None = None) -> Path:
        if configured.is_absolute():
            return configured
        if self.persistent_storage_path is not None and persistent_relative:
            return self.persistent_storage_path / persistent_relative
        return project_root / configured

    def starter_bank_runtime_path(self, project_root: Path) -> Path:
        return self.item_bank_path if self.item_bank_path.is_absolute() else project_root / self.item_bank_path

    def generated_bank_runtime_path(self, project_root: Path) -> Path:
        return self.runtime_path(self.generated_item_bank_path, project_root, "item_bank/generated_items.jsonl")

    def audio_cache_runtime_path(self, project_root: Path) -> Path:
        return self.runtime_path(self.audio_cache_dir, project_root, "cache/audio")

    def session_runtime_path(self, project_root: Path) -> Path:
        return self.runtime_path(self.session_dir, project_root, "sessions")

    def history_runtime_path(self, project_root: Path) -> Path:
        return self.runtime_path(self.history_dir, project_root, "history")

    def quarantine_runtime_path(self, project_root: Path) -> Path:
        return self.runtime_path(self.quarantine_dir, project_root, "quarantine")

    def ensure_directories(self, project_root: Path | None = None) -> None:
        root = project_root or Path.cwd()
        for path in (
            self.generated_bank_runtime_path(root).parent,
            self.audio_cache_runtime_path(root),
            self.session_runtime_path(root),
            self.history_runtime_path(root),
            self.quarantine_runtime_path(root),
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _author_provider_order(self) -> list[str]:
        return {
            "huggingface": ["hf"],
            "groq": ["groq"],
            "hf_then_groq": ["hf", "groq"],
            "groq_then_hf": ["groq", "hf"],
            "mock": ["mock"],
            "disabled": [],
        }[self.generation_provider]

    def verifier_provider_order(self) -> list[str]:
        if self.verification_provider == "auto":
            author = self._author_provider_order()
            # Reverse the author order so a second configured provider is preferred for verification.
            return list(reversed(author))
        return {
            "huggingface": ["hf"],
            "groq": ["groq"],
            "hf_then_groq": ["hf", "groq"],
            "groq_then_hf": ["groq", "hf"],
            "mock": ["mock"],
        }[self.verification_provider]

    def model_warnings(self) -> list[str]:
        warnings: list[str] = []
        deprecated_groq = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}
        if self.groq_model in deprecated_groq or self.groq_verifier_model in deprecated_groq:
            warnings.append(
                "The configured Groq Llama model is scheduled for shutdown on 2026-08-16 for free/developer tiers; use openai/gpt-oss-120b or openai/gpt-oss-20b."
            )
        if self.structured_output_mode == "json_object":
            warnings.append(
                "STRUCTURED_OUTPUT_MODE=json_object disables provider-enforced JSON Schema; auto or strict is safer."
            )
        if self.generation_audit_mode == "off":
            warnings.append(
                "GENERATION_AUDIT_MODE=off skips the independent passage audit; deterministic checks and blind question verification still run."
            )
        author_order = self._author_provider_order()
        verifier_order = self.verifier_provider_order()
        if author_order and verifier_order and author_order[0] == verifier_order[0]:
            provider = author_order[0]
            same_model = (
                provider == "hf" and self.hf_text_model == self.hf_verifier_model
            ) or (
                provider == "groq" and self.groq_model == self.groq_verifier_model
            )
            if same_model:
                warnings.append(
                    "The author and verifier are configured to use the same provider/model, which reduces validator independence."
                )
        return warnings

    def provider_readiness(self) -> tuple[bool, str]:
        if not self.enable_user_generation:
            return False, "User-requested live generation is disabled by configuration."
        if self.generation_provider == "disabled":
            return False, "No live generation provider is enabled. Bank content remains available automatically."
        if self.generation_provider == "mock":
            return True, "Deterministic mock provider enabled for development/testing only."
        order = self._author_provider_order()
        available = ("hf" in order and bool(self.hf_token)) or ("groq" in order and bool(self.groq_api_key))
        if not available:
            return False, "The configured provider has no matching API key/secret. Fresh-AI requests will fall back to the bank."
        warning = " ".join(self.model_warnings())
        message = "Fresh-AI generation is available; accepted items will be audited, independently verified, and saved to the generated bank."
        return True, f"{message} {warning}".strip()


def _optional_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    return Path(raw) if raw else None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw is not None and raw.strip() else default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # GENERATION_PROVIDER is the new name. GENAI_PROVIDER remains a backward-compatible alias
    # for the original repository and existing Hugging Face Space configuration.
    generation_provider = os.getenv("GENERATION_PROVIDER") or os.getenv("GENAI_PROVIDER") or "hf_then_groq"
    settings = Settings(
        environment=os.getenv("APP_ENV", "production"),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        storage_dir=Path(os.getenv("STORAGE_DIR", "storage")),
        item_bank_path=Path(os.getenv("ITEM_BANK_PATH", "data/starter_items.jsonl")),
        generated_item_bank_path=Path(os.getenv("GENERATED_ITEM_BANK_PATH", "storage/item_bank/generated_items.jsonl")),
        audio_cache_dir=Path(os.getenv("AUDIO_CACHE_DIR", "storage/cache/audio")),
        session_dir=Path(os.getenv("SESSION_DIR", "storage/sessions")),
        history_dir=Path(os.getenv("HISTORY_DIR", "storage/history")),
        quarantine_dir=Path(os.getenv("QUARANTINE_DIR", "storage/quarantine")),
        persistent_storage_path=_optional_path("PERSISTENT_STORAGE_PATH"),
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        hf_dataset_repo=os.getenv("HF_DATASET_REPO") or None,
        hf_token=os.getenv("HF_TOKEN") or None,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        generation_provider=generation_provider,
        verification_provider=os.getenv("VERIFICATION_PROVIDER", "auto"),
        enable_user_generation=_env_bool("ENABLE_USER_GENERATION", True),
        hf_provider=os.getenv("HF_PROVIDER", "auto"),
        hf_text_model=os.getenv("HF_TEXT_MODEL", "openai/gpt-oss-120b"),
        hf_verifier_model=os.getenv("HF_VERIFIER_MODEL", "openai/gpt-oss-20b"),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_verifier_model=os.getenv("GROQ_VERIFIER_MODEL", "openai/gpt-oss-20b"),
        structured_output_mode=os.getenv("STRUCTURED_OUTPUT_MODE", "auto"),
        provider_timeout_seconds=int(os.getenv("PROVIDER_TIMEOUT_SECONDS", "45")),
        provider_max_retries=int(os.getenv("PROVIDER_MAX_RETRIES", "2")),
        max_provider_attempts_per_stage=int(os.getenv("MAX_PROVIDER_ATTEMPTS_PER_STAGE", "4")),
        generation_concurrency_limit=int(os.getenv("GENERATION_CONCURRENCY_LIMIT", "1")),
        queue_concurrency_limit=int(os.getenv("QUEUE_CONCURRENCY_LIMIT", "4")),
        max_generation_requests_per_session=int(os.getenv("MAX_GENERATION_REQUESTS_PER_SESSION", "8")),
        generation_repair_attempts=int(os.getenv("GENERATION_REPAIR_ATTEMPTS", "1")),
        generation_audit_mode=os.getenv("GENERATION_AUDIT_MODE", "always"),
        second_verifier_high_risk=_env_bool("SECOND_VERIFIER_HIGH_RISK", True),
        authoring_temperature=_env_float("AUTHORING_TEMPERATURE", 0.25),
        verification_temperature=_env_float("VERIFICATION_TEMPERATURE", 0.0),
        passage_max_tokens=int(os.getenv("PASSAGE_MAX_TOKENS", "3200")),
        question_max_tokens=int(os.getenv("QUESTION_MAX_TOKENS", "2600")),
        repair_max_tokens=int(os.getenv("REPAIR_MAX_TOKENS", "3200")),
        audit_max_tokens=int(os.getenv("AUDIT_MAX_TOKENS", "1200")),
        verifier_max_tokens=int(os.getenv("VERIFIER_MAX_TOKENS", "900")),
        enable_history=_env_bool("ENABLE_HISTORY", True),
        enable_analytics=_env_bool("ENABLE_ANALYTICS", False),
        checkpoint_after_passage=_env_bool("CHECKPOINT_AFTER_PASSAGE", True),
        audio_cache_max_age_days=int(os.getenv("AUDIO_CACHE_MAX_AGE_DAYS", "30")),
        orphan_temp_max_age_hours=int(os.getenv("ORPHAN_TEMP_MAX_AGE_HOURS", "12")),
        edge_tts_voice=os.getenv("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural"),
        edge_tts_rate=os.getenv("EDGE_TTS_RATE", "+0%"),
        app_host=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        app_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    )
    settings.ensure_directories()
    return settings
