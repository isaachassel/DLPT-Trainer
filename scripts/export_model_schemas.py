from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.models import (  # noqa: E402
    AbilityEstimate,
    AdaptiveSelection,
    AudioAsset,
    GenerationMetadata,
    ItemStatistics,
    PassageItem,
    QuestionItem,
    ResponseRecord,
    SessionCheckpoint,
    SessionState,
    UserHistory,
    ValidationReport,
)


MODELS = (
    AbilityEstimate,
    AdaptiveSelection,
    AudioAsset,
    GenerationMetadata,
    ItemStatistics,
    PassageItem,
    QuestionItem,
    ResponseRecord,
    SessionCheckpoint,
    SessionState,
    UserHistory,
    ValidationReport,
)


def main() -> None:
    destination = ROOT / "data/schemas"
    destination.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        target = destination / f"{model.__name__}.schema.json"
        target.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Exported {len(MODELS)} schemas to {destination}")


if __name__ == "__main__":
    main()
