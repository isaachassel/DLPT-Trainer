from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable, Sequence

CANONICAL_TOPICS: tuple[str, ...] = (
    "Accidents and disasters",
    "Commerce",
    "Crime and law enforcement",
    "Culture and society",
    "Daily life",
    "Economics",
    "Education",
    "Environment",
    "Government and politics",
    "International relations",
    "Public health",
    "Public services",
    "Science and technology",
    "Transportation",
    "Workplace",
)

# Ordered from narrow/high-confidence mappings to broader fallbacks.
_TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Transportation", (
        "transport", "transit", "traffic", "vehicle", "bus", "rail", "train", "metro",
        "subway", "station", "platform", "road", "highway", "airport", "aviation",
        "bike", "bicycle", "cycling", "самокат", "велосип", "транспорт", "дорог",
    )),
    ("Public health", (
        "health", "medical", "medicine", "hospital", "clinic", "doctor", "patient",
        "vaccin", "disease", "epidem", "healthcare", "здоров", "медицин", "больниц",
    )),
    ("Education", (
        "education", "school", "student", "teacher", "university", "course", "class",
        "lesson", "training", "образован", "школ", "студент", "университет", "курс",
    )),
    ("Crime and law enforcement", (
        "crime", "police", "fraud", "court", "law enforcement", "arrest", "security service",
        "преступ", "полици", "мошенн", "суд", "задерж",
    )),
    ("International relations", (
        "international", "foreign policy", "diplom", "sanction", "treaty", "alliance",
        "международ", "диплом", "санкц", "договор",
    )),
    ("Government and politics", (
        "government", "politic", "election", "parliament", "ministry", "municipal policy",
        "public policy", "administration", "правитель", "политик", "выбор", "парламент",
    )),
    ("Economics", (
        "econom", "inflation", "budget", "investment", "employment rate", "tax", "finance",
        "эконом", "инфляц", "бюджет", "инвест", "налог", "финанс",
    )),
    ("Commerce", (
        "commerce", "business", "consumer", "retail", "store", "market", "sale", "delivery",
        "package", "company", "торгов", "бизнес", "магазин", "рынок", "достав",
    )),
    ("Environment", (
        "environment", "climate", "pollution", "waste", "recycling", "river", "forest",
        "energy conservation", "эколог", "климат", "загряз", "отход", "переработ",
    )),
    ("Accidents and disasters", (
        "accident", "disaster", "storm", "earthquake", "flood", "fire", "emergency",
        "авари", "катастроф", "шторм", "землетряс", "наводнен", "пожар",
    )),
    ("Workplace", (
        "workplace", "employee", "employer", "office", "shift", "meeting", "equipment maintenance",
        "рабоч", "сотрудник", "офис", "смен", "совещан",
    )),
    ("Culture and society", (
        "culture", "society", "museum", "theater", "theatre", "art", "festival", "library",
        "community event", "community gardening", "культур", "обществ", "музей", "театр", "библиотек",
    )),
    ("Public services", (
        "public service", "public facilities", "community service", "community center",
        "utility", "utilities", "outage", "municipal", "city infrastructure",
        "urban development", "community development", "public information",
        "service announcement", "городск", "коммуналь", "инфраструктур",
    )),
    ("Science and technology", (
        "science", "technology", "research", "robot", "artificial intelligence", "digital",
        "software", "internet", "wi-fi", "wifi", "наук", "технолог", "исследован", "робот",
    )),
    ("Daily life", (
        "daily life", "everyday", "family", "housing", "appointment", "leisure", "routine",
        "повседнев", "семь", "жиль", "досуг",
    )),
)

_STOPWORDS = {
    "about", "after", "before", "from", "into", "near", "with", "without", "city", "local",
    "public", "service", "services", "program", "programme", "new", "community", "urban",
    "the", "and", "for", "that", "this", "its", "their", "announces", "announcement",
    "для", "после", "перед", "город", "новый", "новая", "новое", "общественный",
}


def canonicalize_topic(topic: str | None, subtopic: str | None = None, genre: str | None = None) -> str:
    """Map free-form generated labels to the stable DLPT topic taxonomy."""

    raw_topic = str(topic or "").strip()
    for canonical in CANONICAL_TOPICS:
        if raw_topic.casefold() == canonical.casefold():
            return canonical

    combined = " ".join(part for part in (raw_topic, str(subtopic or ""), str(genre or "")) if part).casefold()
    for canonical, cues in _TOPIC_RULES:
        if any(cue in combined for cue in cues):
            return canonical
    return "Daily life"


def normalize_requested_topics(topics: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for topic in topics or ():
        canonical = canonicalize_topic(topic)
        if canonical not in result:
            result.append(canonical)
    return result


def theme_tokens(*parts: str | None) -> set[str]:
    text = " ".join(str(part or "") for part in parts).casefold()
    tokens = {
        token for token in re.findall(r"[a-zа-яё0-9]{4,}", text)
        if token not in _STOPWORDS
    }
    return tokens


def theme_similarity(a: Sequence[str | None], b: Sequence[str | None]) -> float:
    left = theme_tokens(*a)
    right = theme_tokens(*b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def choose_balanced_topic(
    *,
    requested_topics: Iterable[str] | None,
    existing_topics: Iterable[str],
    recent_topics: Sequence[str],
    nonce: str,
) -> str:
    """Choose a category with strong anti-repetition and exposure balancing."""

    requested = normalize_requested_topics(requested_topics)
    candidates = requested or list(CANONICAL_TOPICS)
    counts = Counter(canonicalize_topic(topic) for topic in existing_topics)
    recent = [canonicalize_topic(topic) for topic in recent_topics]
    recent_rank = {topic: index for index, topic in enumerate(reversed(recent[-6:]))}

    def score(topic: str) -> tuple[int, int, int]:
        # Recent use is punished much more strongly than lifetime exposure.
        recency_penalty = 100 if topic in recent[-3:] else 25 if topic in recent[-6:] else 0
        exposure = counts.get(topic, 0)
        tie = int(hashlib.sha256(f"{nonce}:{topic}".encode("utf-8")).hexdigest()[:8], 16)
        return recency_penalty + exposure, recent_rank.get(topic, 999), tie

    return min(candidates, key=score)
