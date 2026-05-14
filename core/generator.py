from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .prompts import GENERATION_SYSTEM_PROMPT, GENERATION_USER_PROMPT, PASSAGE_LENGTH_GUIDE
from .schema import Question, TestBlock

load_dotenv()


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[start : end + 1])


def _validate_block(data: Dict[str, Any], fallback_level: str, fallback_topic: str) -> TestBlock:
    questions = []
    raw_questions = data.get("questions", [])
    if len(raw_questions) < 4:
        raise ValueError("Generated block has fewer than 4 questions.")

    for i, q in enumerate(raw_questions[:4], start=1):
        choices = q.get("choices", {})
        if not all(k in choices for k in ["A", "B", "C", "D"]):
            raise ValueError("Question choices must include A, B, C, D.")
        correct = str(q.get("correct_answer", "")).strip().upper()
        if correct not in ["A", "B", "C", "D"]:
            raise ValueError("Correct answer must be A, B, C, or D.")
        questions.append(
            Question(
                id=str(q.get("id", f"Q{i}")),
                question=str(q.get("question", "")).strip(),
                choices={k: str(v).strip() for k, v in choices.items()},
                correct_answer=correct,
                explanation=str(q.get("explanation", "")).strip(),
                evidence=str(q.get("evidence", "")).strip(),
                question_type=str(q.get("question_type", "comprehension")).strip(),
            )
        )

    passage_ru = str(data.get("passage_ru", "")).strip()
    word_count = len(passage_ru.split())
    min_words_by_level = {"0+": 70, "1": 110, "1+": 150, "2": 230, "2+": 320, "3": 430}
    min_words = min_words_by_level.get(fallback_level, 150)
    if word_count < min_words:
        raise ValueError(f"Passage is too short for ILR {fallback_level}: {word_count} words, expected at least {min_words}.")

    return TestBlock(
        skill="reading",
        ilr_level=str(data.get("ilr_level", fallback_level)),
        topic=str(data.get("topic", fallback_topic)),
        passage_title=str(data.get("passage_title", "Untitled Passage")),
        passage_ru=passage_ru,
        questions=questions,
    )


def generate_reading_block(level: str, topic: str) -> TestBlock:
    token = os.getenv("HF_TOKEN")
    model = os.getenv("HF_TEXT_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    if token:
        try:
            client = InferenceClient(model=model, token=token)
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": GENERATION_USER_PROMPT.format(level=level, topic=topic, length_guide=PASSAGE_LENGTH_GUIDE.get(level, PASSAGE_LENGTH_GUIDE["2"]))},
                ],
                max_tokens=3600,
                temperature=0.5,
            )
            content = response.choices[0].message.content
            data = _extract_json(content)
            return _validate_block(data, level, topic)
        except Exception as exc:
            print(f"Generation failed, using demo fallback: {exc}")

    return demo_reading_block(level, topic)


def demo_reading_block(level: str, topic: str) -> TestBlock:
    """Fallback block so the app runs without secrets during setup/testing."""
    variants = [
        {
            "passage_title": "Regional Infrastructure Disruption",
            "passage_ru": (
                "В администрации Приморского края сообщили, что движение по одной из региональных трасс "
                "было временно ограничено после сильного дождя и схода грунта возле небольшого моста. "
                "По словам представителей дорожной службы, повреждение не является критическим, однако "
                "специалисты решили закрыть участок до завершения проверки опор. Местным жителям рекомендовали "
                "пользоваться объездной дорогой через соседний район, хотя этот маршрут занимает примерно на сорок минут больше. "
                "Несколько автобусных рейсов были перенесены на более позднее время. Власти подчеркнули, что решение "
                "принято не из-за полного разрушения моста, а из-за риска дальнейшего размыва почвы, если осадки продолжатся."
            ),
            "questions": [
                {
                    "id": "Q1",
                    "question": "What was the main reason the road section was closed?",
                    "choices": {
                        "A": "A bridge had completely collapsed.",
                        "B": "Officials wanted to inspect the supports after soil erosion.",
                        "C": "Bus drivers refused to use the route.",
                        "D": "The road was being expanded for construction."
                    },
                    "correct_answer": "B",
                    "explanation": "The passage says the damage was not critical, but officials closed the section to inspect the supports and prevent risk from further erosion.",
                    "evidence": "закрыть участок до завершения проверки опор... риск дальнейшего размыва почвы",
                    "question_type": "cause and effect"
                },
                {
                    "id": "Q2",
                    "question": "What did residents have to do while the road was restricted?",
                    "choices": {
                        "A": "Use a longer alternate route.",
                        "B": "Cancel all travel outside the district.",
                        "C": "Cross the bridge on foot only.",
                        "D": "Wait for military engineers."
                    },
                    "correct_answer": "A",
                    "explanation": "Residents were told to use a bypass road through a neighboring district, which took about forty minutes longer.",
                    "evidence": "пользоваться объездной дорогой через соседний район... на сорок минут больше",
                    "question_type": "detail"
                },
                {
                    "id": "Q3",
                    "question": "Which conclusion is best supported by the passage?",
                    "choices": {
                        "A": "The authorities were responding cautiously to a potential safety risk.",
                        "B": "The road closure was mainly political.",
                        "C": "The bridge was destroyed beyond repair.",
                        "D": "Public transportation was permanently suspended."
                    },
                    "correct_answer": "A",
                    "explanation": "The text stresses that the damage was not critical, but officials acted because further rainfall could increase the risk.",
                    "evidence": "не является критическим... из-за риска дальнейшего размыва почвы",
                    "question_type": "inference"
                },
                {
                    "id": "Q4",
                    "question": "What happened to several bus routes?",
                    "choices": {
                        "A": "They were cancelled for the entire week.",
                        "B": "They were moved to later times.",
                        "C": "They were redirected through another country.",
                        "D": "They continued without any change."
                    },
                    "correct_answer": "B",
                    "explanation": "The passage states that several bus trips were rescheduled for a later time.",
                    "evidence": "Несколько автобусных рейсов были перенесены на более позднее время.",
                    "question_type": "detail"
                }
            ]
        }
    ]
    data = random.choice(variants)
    data.update({"skill": "reading", "ilr_level": level, "topic": topic})
    return _validate_block(data, level, topic)
