from __future__ import annotations

from collections import Counter, defaultdict

from .constants import ILR_THETA
from .models import AbilityEstimate, ResponseRecord



def nearest_ilr_band(difficulty: float) -> str:
    """Map a continuous item difficulty to the nearest displayed ILR half-band."""
    return min(ILR_THETA, key=lambda level: abs(ILR_THETA[level] - difficulty))


def item_level_label(record: ResponseRecord) -> str:
    """Describe an item's level without overstating provisional metadata."""
    if record.provisional_item:
        return f"Intended ILR {record.target_ilr} — provisional item level"
    operational = nearest_ilr_band(record.item_difficulty)
    if operational == record.target_ilr:
        return f"Approximately ILR {operational} — empirically calibrated item difficulty"
    return (
        f"Approximately ILR {operational} — empirically calibrated item difficulty; "
        f"original authoring target ILR {record.target_ilr}"
    )

def estimate_label(estimate: AbilityEstimate) -> str:
    if estimate.practice_ilr is None or not estimate.stable:
        return "Insufficient evidence for a stable estimate."
    qualifier = "Provisional practice estimate" if estimate.provisional else "Practice estimate"
    return f"{qualifier}: ILR {estimate.practice_ilr}, with {estimate.confidence} confidence."


def accuracy(records: list[ResponseRecord]) -> tuple[int, int, float]:
    attempted = len(records)
    correct = sum(record.is_correct for record in records)
    return correct, attempted, (correct / attempted if attempted else 0.0)


def grouped_accuracy(records: list[ResponseRecord], attribute: str) -> dict[str, tuple[int, int, float]]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        grouped[str(getattr(record, attribute))].append(record.is_correct)
    return {
        key: (sum(values), len(values), sum(values) / len(values))
        for key, values in sorted(grouped.items())
    }


def response_time_summary(records: list[ResponseRecord]) -> dict[str, float]:
    if not records:
        return {"mean": 0.0, "median": 0.0, "max": 0.0}
    values = sorted(record.response_time_seconds for record in records)
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
    return {"mean": sum(values) / len(values), "median": median, "max": max(values)}


def strengths_and_weaknesses(records: list[ResponseRecord]) -> tuple[list[str], list[str]]:
    grouped = grouped_accuracy(records, "question_type")
    qualified = [(name, values) for name, values in grouped.items() if values[1] >= 2]
    strongest = [name for name, _ in sorted(qualified, key=lambda x: (x[1][2], x[1][1]), reverse=True)[:3]]
    weakest = [name for name, _ in sorted(qualified, key=lambda x: (x[1][2], -x[1][1]))[:3]]
    return strongest, weakest
