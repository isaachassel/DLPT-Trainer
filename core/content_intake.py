"""Portable contributor format; converts to unapproved local workshop drafts."""
from typing import Literal

from pydantic import Field, model_validator

from .constants import ILR_THETA
from .models import GenerationMetadata, PassageItem, QuestionItem, StrictModel
from .preset_bank import ContentItem, ContentPackage, Review, reject_secret_fields
from .validation import content_hash, target_unit_count, validate_passage, validate_question


class IntakeSource(StrictModel):
    title: str = Field(min_length=1)
    creator: str = "Unknown"
    locator: str = Field(min_length=1, description="Public URL or source filename plus page/time range")
    date: str = "Unknown"
    rights: str = Field(min_length=1, description="Exact license/permission or Unknown; do not infer")
    attribution: str = "Unknown"
    modifications: str = Field(min_length=1)


class IntakeQuestion(StrictModel):
    stem_en: str = Field(min_length=8)
    choices: dict[str, str]
    correct_key: Literal['A', 'B', 'C', 'D']
    rationale_en: str = Field(min_length=12)
    evidence: str = Field(min_length=1, description="Exact short excerpt in the source language")
    question_type: Literal['main idea', 'prominent detail', 'inference', 'speaker/writer intent',
                           'tone or attitude', 'reference', 'sequence', 'cause and effect',
                           'relationship of ideas', 'meaning from context']
    origin: Literal['copied', 'adapted', 'human-authored', 'AI-authored']


class IntakeItem(StrictModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    language: Literal['ru', 'zh-CN']
    skill: Literal['reading', 'listening']
    target_ilr: Literal['0', '0+', '1', '1+', '2', '2+', '3']
    difficulty_rationale: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    orientation_en: str = Field(min_length=10)
    text: str = Field(min_length=1, description="Verbatim passage or listening transcript; preserve paragraphs")
    source_type: Literal['authentic/open-licensed', 'transformed/adapted', 'synthetic']
    source: IntakeSource
    questions: list[IntakeQuestion] = Field(min_length=1, max_length=5)
    audio_file: str | None = Field(default=None, description="Optional relative audio/ path, retained for review only")
    notes: str = ""

    @model_validator(mode='after')
    def check_media(self):
        if self.skill == 'listening' and len(self.questions) > 3:
            raise ValueError('Listening passages support 1–3 questions')
        if self.audio_file:
            parts = self.audio_file.split('/')
            if (self.skill != 'listening' or parts[0] != 'audio' or
                    any(p in ('', '.', '..') for p in parts) or
                    ':' in self.audio_file or '\\' in self.audio_file or
                    not self.audio_file.lower().endswith(('.mp3', '.wav', '.m4a'))):
                raise ValueError('Audio must use a safe relative audio/ filename for listening')
        return self


class IntakePackage(StrictModel):
    format: Literal['dlpt-contributor-v1'] = 'dlpt-contributor-v1'
    items: list[IntakeItem] = Field(min_length=1, max_length=500)

    @model_validator(mode='before')
    @classmethod
    def no_credentials(cls, value):
        reject_secret_fields(value)
        return value


def convert_package(package: IntakePackage) -> tuple[ContentPackage, list[dict]]:
    """No file copying, publication, approval, generation, or network access."""
    items, findings = [], []
    for source in package.items:
        metadata = GenerationMetadata(provider='contributor import', model='unspecified',
            prompt_version='dlpt-contributor-v1',
            authoring_notes='Imported source material; question origins recorded separately. Pending curator review.')
        questions = [QuestionItem(id=f'{source.id}_q{n}', passage_id=source.id,
            stem_en=q.stem_en, choices=q.choices, correct_key=q.correct_key,
            rationale_en=q.rationale_en, evidence_ru=q.evidence, question_type=q.question_type,
            target_ilr=source.target_ilr, provisional_difficulty=ILR_THETA[source.target_ilr],
            generation=metadata.model_copy(update={'authoring_notes': f'Question origin: {q.origin}'}))
            for n, q in enumerate(source.questions, 1)]
        digest = content_hash(source.text)
        passage = PassageItem(id=source.id, language=source.language, skill=source.skill,
            target_ilr=source.target_ilr, provisional_difficulty=ILR_THETA[source.target_ilr],
            genre=source.genre, topic=source.topic, subtopic=source.genre,
            orientation_en=source.orientation_en, passage_ru=source.text,
            source_type=source.source_type, license=source.source.rights,
            provenance={**{f'source_{k}': v for k, v in source.source.model_dump().items()},
                        'difficulty_rationale': source.difficulty_rationale,
                        'contributor_notes': source.notes,
                        'candidate_audio_file': source.audio_file or ''},
            word_count=target_unit_count(source.text, source.language),
            question_ids=[q.id for q in questions], content_hash=digest,
            duplicate_detection_hash=digest, generation=metadata)
        reports = [validate_passage(passage, questions), *[validate_question(q, passage) for q in questions]]
        issues = sorted({s for r in reports for s in r.failure_reasons + r.ambiguity_flags})
        if source.skill == 'listening':
            issues.append('Recording requires separate ingestion, transcript matching and licensing review')
        findings.append({'id': source.id, 'checks_to_review': issues,
                         'review': 'draft; source rights, language, questions and ILR require review'})
        passage.validation_status = 'needs_review'
        for q in questions:
            q.validation_status = 'needs_review'
        items.append(ContentItem(id=source.id, passage=passage, questions=questions,
            review=Review(notes='Contributor import: pending source rights, language, question, ILR and audio review.')))
    # Enforces unique IDs across the entire batch. Never marks items approved.
    return ContentPackage(items=items), findings
