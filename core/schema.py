from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ILR_LEVELS = ["0+", "1", "1+", "2", "2+", "3"]

QUESTION_TYPES = [
    "main idea",
    "detail",
    "inference",
    "speaker/writer intent",
    "cause and effect",
    "sequence",
    "tone or attitude",
    "meaning from context",
]

@dataclass
class Question:
    id: str
    question: str
    choices: Dict[str, str]
    correct_answer: str
    explanation: str
    evidence: str
    question_type: str

@dataclass
class TestBlock:
    skill: str
    ilr_level: str
    topic: str
    passage_title: str
    passage_ru: str
    questions: List[Question]
    generation_source: str = "live"
    generation_error: str = ""

@dataclass
class AnswerRecord:
    block_number: int
    skill: str
    ilr_level: str
    topic: str
    passage_title: str
    passage_ru: str
    question: Question
    selected_answer: Optional[str]
    is_correct: bool

@dataclass
class SessionState:
    mode: str
    starting_level: str
    current_level: str
    target_level: str
    session_questions: int
    base_session_questions: int
    timer_mode: str
    topic: str
    block_number: int = 0
    current_block: Optional[TestBlock] = None
    records: List[AnswerRecord] = field(default_factory=list)
    recent_block_scores: List[float] = field(default_factory=list)
    adaptive_note: str = "Adaptive engine active. Your level may change after each block based on performance."

    @property
    def answered_count(self) -> int:
        return len(self.records)

    @property
    def is_complete(self) -> bool:
        return self.answered_count >= self.session_questions
