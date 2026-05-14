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

MIN_WORDS_BY_LEVEL = {"0+": 70, "1": 110, "1+": 150, "2": 230, "2+": 320, "3": 430}


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[start : end + 1])


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _validate_block(data: Dict[str, Any], fallback_level: str, fallback_topic: str, enforce_length: bool = True) -> TestBlock:
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
    min_words = MIN_WORDS_BY_LEVEL.get(fallback_level, 150)
    word_count = _word_count(passage_ru)
    if enforce_length and word_count < min_words:
        raise ValueError(
            f"Passage is too short for ILR {fallback_level}: {word_count} words, expected at least {min_words}."
        )

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
        last_error = None
        for attempt in range(2):
            try:
                client = InferenceClient(model=model, token=token)
                prompt = GENERATION_USER_PROMPT.format(
                    level=level,
                    topic=topic,
                    length_guide=PASSAGE_LENGTH_GUIDE.get(level, PASSAGE_LENGTH_GUIDE["2"]),
                )
                if attempt == 1:
                    prompt += (
                        "\n\nIMPORTANT RETRY: The previous passage was too short or invalid. "
                        f"Write at least {MIN_WORDS_BY_LEVEL.get(level, 150)} Russian words in passage_ru. "
                        "Return valid JSON only."
                    )
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=4200,
                    temperature=0.45,
                )
                content = response.choices[0].message.content
                data = _extract_json(content)
                return _validate_block(data, level, topic, enforce_length=True)
            except Exception as exc:
                last_error = exc
                print(f"Generation attempt {attempt + 1} failed: {exc}")
        print(f"Generation failed after retries, using demo fallback: {last_error}")

    return demo_reading_block(level, topic)


def _expand_demo_passage(base: str, level: str) -> str:
    """Make the demo fallback long enough for the stricter ILR length checks."""
    additions = {
        "0+": "",
        "1": " Представители администрации заявили, что дополнительная информация будет опубликована после осмотра участка.",
        "1+": (
            " Представители администрации заявили, что дополнительная информация будет опубликована после осмотра участка. "
            "Они также отметили, что ограничение движения носит временный характер и может быть снято, если специалисты не обнаружат новых повреждений."
        ),
        "2": (
            " Представители администрации заявили, что дополнительная информация будет опубликована после осмотра участка. "
            "Они также отметили, что ограничение движения носит временный характер и может быть снято, если специалисты не обнаружат новых повреждений. "
            "Между тем часть жителей выразила недовольство тем, что предупреждение появилось только утром, когда многие уже выехали на работу. "
            "В дорожной службе ответили, что решение принималось ночью после повторного осмотра, поэтому заранее уведомить всех водителей было невозможно."
        ),
        "2+": (
            " Представители администрации заявили, что дополнительная информация будет опубликована после осмотра участка. "
            "Они также отметили, что ограничение движения носит временный характер и может быть снято, если специалисты не обнаружат новых повреждений. "
            "Между тем часть жителей выразила недовольство тем, что предупреждение появилось только утром, когда многие уже выехали на работу. "
            "В дорожной службе ответили, что решение принималось ночью после повторного осмотра, поэтому заранее уведомить всех водителей было невозможно. "
            "Эксперты считают, что ситуация показывает более широкую проблему: многие малые мосты в регионе строились десятилетия назад и требуют регулярного контроля, особенно после сильных осадков. "
            "При этом чиновники избегают говорить о капитальном ремонте, подчеркивая, что сейчас речь идет только о безопасности конкретного участка."
        ),
        "3": (
            " Представители администрации заявили, что дополнительная информация будет опубликована после осмотра участка. "
            "Они также отметили, что ограничение движения носит временный характер и может быть снято, если специалисты не обнаружат новых повреждений. "
            "Между тем часть жителей выразила недовольство тем, что предупреждение появилось только утром, когда многие уже выехали на работу. "
            "В дорожной службе ответили, что решение принималось ночью после повторного осмотра, поэтому заранее уведомить всех водителей было невозможно. "
            "Эксперты считают, что ситуация показывает более широкую проблему: многие малые мосты в регионе строились десятилетия назад и требуют регулярного контроля, особенно после сильных осадков. "
            "При этом чиновники избегают говорить о капитальном ремонте, подчеркивая, что сейчас речь идет только о безопасности конкретного участка. "
            "Наблюдатели отмечают, что подобные решения часто ставят местные власти перед выбором между неудобством для населения и риском быть обвиненными в бездействии, если произойдет авария. "
            "Поэтому временное закрытие дороги можно рассматривать не только как техническую меру, но и как попытку снизить административную ответственность на фоне растущего внимания к состоянию региональной инфраструктуры."
        ),
    }
    passage = base + additions.get(level, additions["2"])
    # Last-resort padding, so fallback can never crash the app.
    min_words = MIN_WORDS_BY_LEVEL.get(level, 150)
    safety_sentence = (
        " Власти сообщили, что окончательное решение будет принято после проверки, а жителям рекомендуют заранее планировать поездки и следить за обновлениями."
    )
    while _word_count(passage) < min_words:
        passage += safety_sentence
    return passage


def demo_reading_block(level: str, topic: str) -> TestBlock:
    """Fallback block so the app runs without secrets or when model output fails."""
    base_passage = (
        "В администрации Приморского края сообщили, что движение по одной из региональных трасс "
        "было временно ограничено после сильного дождя и схода грунта возле небольшого моста. "
        "По словам представителей дорожной службы, повреждение не является критическим, однако "
        "специалисты решили закрыть участок до завершения проверки опор. Местным жителям рекомендовали "
        "пользоваться объездной дорогой через соседний район, хотя этот маршрут занимает примерно на сорок минут больше. "
        "Несколько автобусных рейсов были перенесены на более позднее время. Власти подчеркнули, что решение "
        "принято не из-за полного разрушения моста, а из-за риска дальнейшего размыва почвы, если осадки продолжатся."
    )
    data = {
        "passage_title": "Regional Infrastructure Disruption",
        "passage_ru": _expand_demo_passage(base_passage, level),
        "skill": "reading",
        "ilr_level": level,
        "topic": topic,
        "questions": [
            {
                "id": "Q1",
                "question": "What was the main reason the road section was closed?",
                "choices": {
                    "A": "A bridge had completely collapsed.",
                    "B": "Officials wanted to inspect the supports after soil erosion.",
                    "C": "Bus drivers refused to use the route.",
                    "D": "The road was being expanded for construction.",
                },
                "correct_answer": "B",
                "explanation": "The passage says the damage was not critical, but officials closed the section to inspect the supports and reduce risk from further erosion.",
                "evidence": "закрыть участок до завершения проверки опор... риск дальнейшего размыва почвы",
                "question_type": "cause and effect",
            },
            {
                "id": "Q2",
                "question": "What did residents have to do while the road was restricted?",
                "choices": {
                    "A": "Use a longer alternate route.",
                    "B": "Cancel all travel outside the district.",
                    "C": "Cross the bridge on foot only.",
                    "D": "Wait for military engineers.",
                },
                "correct_answer": "A",
                "explanation": "Residents were told to use a bypass road through a neighboring district, which took about forty minutes longer.",
                "evidence": "пользоваться объездной дорогой через соседний район... на сорок минут больше",
                "question_type": "detail",
            },
            {
                "id": "Q3",
                "question": "Which conclusion is best supported by the passage?",
                "choices": {
                    "A": "The authorities were responding cautiously to a potential safety risk.",
                    "B": "The road closure was mainly political.",
                    "C": "The bridge was destroyed beyond repair.",
                    "D": "Public transportation was permanently suspended.",
                },
                "correct_answer": "A",
                "explanation": "The text stresses that the damage was not critical, but officials acted because further rainfall could increase the risk.",
                "evidence": "не является критическим... из-за риска дальнейшего размыва почвы",
                "question_type": "inference",
            },
            {
                "id": "Q4",
                "question": "What happened to several bus routes?",
                "choices": {
                    "A": "They were cancelled for the entire week.",
                    "B": "They were moved to later times.",
                    "C": "They were redirected through another country.",
                    "D": "They continued without any change.",
                },
                "correct_answer": "B",
                "explanation": "The passage states that several bus trips were rescheduled for a later time.",
                "evidence": "Несколько автобусных рейсов были перенесены на более позднее время.",
                "question_type": "detail",
            },
        ],
    }
    # Fallback should never be allowed to crash the app. It is already expanded to target length.
    return _validate_block(data, level, topic, enforce_length=False)
