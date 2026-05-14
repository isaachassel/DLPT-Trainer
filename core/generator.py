from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .prompts import GENERATION_SYSTEM_PROMPT, GENERATION_USER_PROMPT, PASSAGE_LENGTH_GUIDE
from .schema import Question, TestBlock

load_dotenv()

# Minimum quality thresholds. These are intentionally lower than the prompt ranges
# because word counts vary by tokenizer/model, but they still prevent tiny passages.
MIN_WORDS_BY_LEVEL = {"0+": 70, "1": 110, "1+": 150, "2": 230, "2+": 320, "3": 430}

# Give the model enough room to write the passage, questions, choices, answer key,
# explanations, and evidence while still returning valid JSON.
MAX_TOKENS_BY_LEVEL = {
    "0+": 1800,
    "1": 2200,
    "1+": 2800,
    "2": 4200,
    "2+": 5600,
    "3": 7200,
}

_FALLBACK_INDEX = 0


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return a complete JSON object.")
    return json.loads(text[start : end + 1])


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _has_bad_repetition(text: str) -> bool:
    # Reject obvious accidental repeated final sentences from model padding.
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if p.strip()]
    if len(parts) < 2:
        return False
    return any(parts[i] == parts[i - 1] for i in range(1, len(parts)))


def _validate_block(
    data: Dict[str, Any],
    fallback_level: str,
    fallback_topic: str,
    enforce_length: bool = True,
    generation_source: str = "live",
    generation_error: str = "",
) -> TestBlock:
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
        question_text = str(q.get("question", "")).strip()
        if not question_text:
            raise ValueError("Question text cannot be empty.")
        questions.append(
            Question(
                id=str(q.get("id", f"Q{i}")),
                question=question_text,
                choices={k: str(v).strip() for k, v in choices.items()},
                correct_answer=correct,
                explanation=str(q.get("explanation", "")).strip(),
                evidence=str(q.get("evidence", "")).strip(),
                question_type=str(q.get("question_type", "comprehension")).strip(),
            )
        )

    passage_ru = str(data.get("passage_ru", "")).strip()
    if not passage_ru:
        raise ValueError("Generated passage is empty.")

    min_words = MIN_WORDS_BY_LEVEL.get(fallback_level, 150)
    word_count = _word_count(passage_ru)
    if enforce_length and word_count < min_words:
        raise ValueError(
            f"Passage is too short for ILR {fallback_level}: {word_count} words, expected at least {min_words}."
        )
    if enforce_length and _has_bad_repetition(passage_ru):
        raise ValueError("Passage contains repeated consecutive sentences.")

    return TestBlock(
        skill="reading",
        ilr_level=str(data.get("ilr_level", fallback_level)),
        topic=str(data.get("topic", fallback_topic)),
        passage_title=str(data.get("passage_title", "Untitled Passage")),
        passage_ru=passage_ru,
        questions=questions,
        generation_source=generation_source,
        generation_error=generation_error,
    )


def _build_prompt(level: str, topic: str, attempt: int) -> str:
    nonce = f"{int(time.time())}-{random.randint(100000, 999999)}"
    prompt = GENERATION_USER_PROMPT.format(
        level=level,
        topic=topic,
        length_guide=PASSAGE_LENGTH_GUIDE.get(level, PASSAGE_LENGTH_GUIDE["2"]),
    )
    prompt += (
        "\n\nGeneration ID: " + nonce +
        "\nCreate a fresh, non-recycled passage. Do not reuse earlier fallback/demo topics such as "
        "regional infrastructure disruption, labor law changes, gas leaks, or generic road closures unless the user specifically chose that topic. "
        "Do not repeat the same sentence to reach the word count. Return one complete JSON object only."
    )
    if attempt > 0:
        prompt += (
            "\n\nRETRY REQUIREMENT: The previous model output was invalid, too short, incomplete, or repetitive. "
            f"The passage_ru field must contain at least {MIN_WORDS_BY_LEVEL.get(level, 150)} Russian words. "
            "Use enough detail to match the requested ILR level. Return valid JSON only."
        )
    return prompt


def _make_client(token: str) -> InferenceClient:
    provider = os.getenv("HF_PROVIDER", "auto").strip() or "auto"
    try:
        return InferenceClient(provider=provider, token=token)
    except TypeError:
        # Older huggingface_hub versions do not accept provider.
        return InferenceClient(token=token)


def _call_hf_chat(client: InferenceClient, model: str, messages: List[Dict[str, str]], max_tokens: int):
    # Newer HF InferenceClient expects model in the create() call.
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            top_p=0.9,
        )
    except TypeError as first_error:
        # Older versions may have the model bound at client construction.
        try:
            legacy_client = InferenceClient(model=model, token=os.getenv("HF_TOKEN"))
            return legacy_client.chat.completions.create(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
            )
        except Exception:
            raise first_error


def generate_reading_block(level: str, topic: str) -> TestBlock:
    token = os.getenv("HF_TOKEN")
    model = os.getenv("HF_TEXT_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    max_tokens = int(os.getenv("HF_MAX_TOKENS", MAX_TOKENS_BY_LEVEL.get(level, 4200)))

    if token:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                client = _make_client(token)
                messages = [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_prompt(level, topic, attempt)},
                ]
                print(f"Generating live block | model={model} | level={level} | max_tokens={max_tokens} | attempt={attempt + 1}")
                response = _call_hf_chat(client, model, messages, max_tokens)
                content = response.choices[0].message.content
                data = _extract_json(content)
                return _validate_block(data, level, topic, enforce_length=True, generation_source="live")
            except Exception as exc:
                last_error = exc
                print(f"Generation attempt {attempt + 1} failed: {type(exc).__name__}: {exc}")
        error_text = f"Live generation failed after 3 attempts: {type(last_error).__name__}: {last_error}"
        print(error_text)
        return demo_reading_block(level, topic, generation_error=error_text)

    return demo_reading_block(level, topic, generation_error="HF_TOKEN is missing. Add it as a Space secret to enable live AI generation.")


def _pad_to_level(passage: str, level: str) -> str:
    min_words = MIN_WORDS_BY_LEVEL.get(level, 150)
    padders = [
        " По словам местных представителей, дополнительные сведения будут опубликованы после завершения проверки и согласования с профильными службами.",
        " Жителям рекомендовали следить за официальными сообщениями, поскольку предварительные данные могут измениться после осмотра на месте.",
        " Власти подчеркнули, что решение носит временный характер и направлено прежде всего на снижение риска для населения.",
        " Некоторые жители выразили недовольство задержками, однако специалисты заявили, что окончательные выводы можно делать только после полной оценки ситуации.",
        " Наблюдатели отметили, что подобные случаи часто выявляют более широкие проблемы планирования, связи между ведомствами и готовности к внештатным обстоятельствам.",
        " Поэтому ситуация рассматривается не только как отдельный инцидент, но и как проверка способности местных органов быстро информировать население и координировать действия служб.",
    ]
    i = 0
    while _word_count(passage) < min_words:
        passage += padders[i % len(padders)]
        i += 1
    return passage


def _fallback_templates(topic: str) -> List[Dict[str, Any]]:
    """Several fallback blocks so demo mode does not repeat the same passage every block."""
    return [
        {
            "passage_title": "Temporary Evacuation After Gas Leak",
            "passage_ru": (
                "В одном из районов Екатеринбурга жильцов многоквартирного дома временно эвакуировали после сообщения о запахе газа в подъезде. "
                "Аварийная служба прибыла на место через несколько минут и перекрыла подачу газа до завершения проверки. "
                "По предварительным данным, серьезного повреждения оборудования обнаружено не было, однако специалисты решили осмотреть подвальное помещение и несколько квартир на первом этаже. "
                "Жителям разрешили вернуться домой только после проветривания подъезда и повторного замера воздуха. "
                "Представитель администрации сообщил, что эвакуация была профилактической мерой, поскольку в подобных ситуациях задержка может привести к тяжелым последствиям. "
                "Несколько семей временно разместили в соседней школе, где им предложили горячий чай и возможность зарядить телефоны."
            ),
            "questions": [
                {"id":"Q1","question":"Why were residents evacuated?","choices":{"A":"Because a fire destroyed the building.","B":"Because there was a reported smell of gas.","C":"Because the building was being demolished.","D":"Because residents requested a drill."},"correct_answer":"B","explanation":"The passage says residents were evacuated after a report of a gas smell in the entrance.","evidence":"после сообщения о запахе газа","question_type":"detail"},
                {"id":"Q2","question":"What did emergency workers do first?","choices":{"A":"They shut off the gas supply.","B":"They arrested the building manager.","C":"They ordered residents to leave the city.","D":"They repaired the school."},"correct_answer":"A","explanation":"The emergency service shut off gas until the inspection was complete.","evidence":"перекрыла подачу газа до завершения проверки","question_type":"sequence"},
                {"id":"Q3","question":"What can be inferred about the evacuation?","choices":{"A":"It was mainly a precautionary safety measure.","B":"It happened after an explosion.","C":"It was caused by a political protest.","D":"It was permanent."},"correct_answer":"A","explanation":"Officials said no serious damage was initially found, but evacuation was preventive.","evidence":"серьезного повреждения... не было... эвакуация была профилактической мерой","question_type":"inference"},
                {"id":"Q4","question":"Where were some families temporarily placed?","choices":{"A":"In a nearby school.","B":"At a train station.","C":"In a hospital ward.","D":"At city hall overnight."},"correct_answer":"A","explanation":"The passage says several families were temporarily placed in a neighboring school.","evidence":"Несколько семей временно разместили в соседней школе","question_type":"detail"},
            ],
        },
        {
            "passage_title": "Flooding Disrupts Local Rail Service",
            "passage_ru": (
                "В Новосибирской области несколько пригородных поездов задержали после того, как талая вода частично затопила участок железнодорожного полотна. "
                "Представители железной дороги сообщили, что движение не остановлено полностью, но скорость поездов на проблемном участке временно снижена. "
                "Пассажирам рекомендовали заранее проверять расписание, поскольку время прибытия может меняться в течение дня. "
                "По словам инженеров, основная опасность связана не с уровнем воды, а с возможным ослаблением насыпи под путями. "
                "Рабочие начали откачку воды и установили дополнительные датчики, чтобы следить за состоянием грунта. "
                "Местные власти заявили, что ситуация находится под контролем, но предупредили, что новые осадки могут осложнить восстановительные работы."
            ),
            "questions": [
                {"id":"Q1","question":"What caused delays to local trains?","choices":{"A":"A strike by train operators.","B":"Flooding from meltwater near the tracks.","C":"A shortage of tickets.","D":"Closure of the central station."},"correct_answer":"B","explanation":"The passage states meltwater partially flooded part of the rail bed.","evidence":"талая вода частично затопила участок железнодорожного полотна","question_type":"cause and effect"},
                {"id":"Q2","question":"What was temporarily reduced?","choices":{"A":"The train speed on the affected section.","B":"The number of engineers in the region.","C":"The price of tickets.","D":"The length of all routes."},"correct_answer":"A","explanation":"Rail officials said train speed was temporarily reduced on the problem section.","evidence":"скорость поездов... временно снижена","question_type":"detail"},
                {"id":"Q3","question":"What was the main technical concern?","choices":{"A":"Possible weakening of the embankment under the tracks.","B":"Failure of ticket machines.","C":"Loss of passenger documents.","D":"A lack of train cars."},"correct_answer":"A","explanation":"Engineers said the main danger was possible weakening of the ground under the tracks.","evidence":"возможным ослаблением насыпи под путями","question_type":"detail"},
                {"id":"Q4","question":"What could make recovery work more difficult?","choices":{"A":"Additional rainfall.","B":"A change in school schedules.","C":"A shortage of passengers.","D":"A new holiday."},"correct_answer":"A","explanation":"Authorities warned that new precipitation could complicate restoration work.","evidence":"новые осадки могут осложнить восстановительные работы","question_type":"inference"},
            ],
        },
        {
            "passage_title": "Factory Incident Under Review",
            "passage_ru": (
                "В Калужской области комиссия начала проверку после инцидента на небольшом промышленном предприятии, где несколько работников почувствовали недомогание во время ночной смены. "
                "По словам руководства завода, производство было приостановлено на два часа, пока специалисты проверяли систему вентиляции и качество воздуха в цехе. "
                "Медики осмотрели сотрудников на месте; двоих направили в больницу для дополнительного наблюдения, хотя их состояние оценили как стабильное. "
                "Предварительная версия связана с неправильной работой одного из фильтров, однако окончательные выводы будут сделаны после лабораторного анализа. "
                "Профсоюз предприятия потребовал опубликовать результаты проверки, заявив, что работники должны понимать, была ли угроза повторения инцидента. "
                "Администрация пообещала провести дополнительный инструктаж по безопасности."
            ),
            "questions": [
                {"id":"Q1","question":"Why did the commission begin a review?","choices":{"A":"Several workers felt ill during a night shift.","B":"The factory closed permanently.","C":"Workers demanded higher wages only.","D":"A fire destroyed the entire plant."},"correct_answer":"A","explanation":"The review began after several workers felt unwell during the night shift.","evidence":"несколько работников почувствовали недомогание во время ночной смены","question_type":"main idea"},
                {"id":"Q2","question":"What did specialists check?","choices":{"A":"Ventilation and air quality.","B":"Employee bank accounts.","C":"Road conditions near the factory.","D":"School safety rules."},"correct_answer":"A","explanation":"Production stopped while specialists checked the ventilation system and air quality.","evidence":"проверяли систему вентиляции и качество воздуха","question_type":"detail"},
                {"id":"Q3","question":"What is the preliminary explanation?","choices":{"A":"A filter may have malfunctioned.","B":"The workers staged the incident.","C":"There was no night shift.","D":"The hospital caused the problem."},"correct_answer":"A","explanation":"The preliminary version is connected to incorrect operation of one filter.","evidence":"с неправильной работой одного из фильтров","question_type":"detail"},
                {"id":"Q4","question":"Why did the union want the results published?","choices":{"A":"So workers could know whether the incident might happen again.","B":"So the factory could advertise its products.","C":"So the hospital could hire more doctors.","D":"So night shifts could be banned nationwide."},"correct_answer":"A","explanation":"The union said workers needed to understand whether there was a risk of recurrence.","evidence":"работники должны понимать, была ли угроза повторения инцидента","question_type":"speaker/writer intent"},
            ],
        },
    ]


def demo_reading_block(level: str, topic: str, generation_error: str = "") -> TestBlock:
    """Fallback block so the app runs without secrets or when model output fails."""
    global _FALLBACK_INDEX
    templates = _fallback_templates(topic)
    template = templates[_FALLBACK_INDEX % len(templates)]
    _FALLBACK_INDEX += 1
    data = dict(template)
    data["passage_ru"] = _pad_to_level(data["passage_ru"], level)
    data["skill"] = "reading"
    data["ilr_level"] = level
    data["topic"] = topic
    # Fallback should never crash the app. It is padded and length enforcement is disabled here.
    return _validate_block(data, level, topic, enforce_length=False, generation_source="fallback", generation_error=generation_error)
