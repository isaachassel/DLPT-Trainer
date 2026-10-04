from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import get_settings
from core.generation import LiveGenerationService
from core.preset_bank import PracticeBank


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Administrator item authoring. Accepted items are validated and appended to the generated-bank overlay."
    )
    parser.add_argument("--skill", choices=["reading", "listening"], required=True)
    parser.add_argument("--level", required=True)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--mode", choices=["training", "diagnostic", "simulation"], default="training")
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--competency", action="append", default=[])
    parser.add_argument("--max-questions", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_directories(ROOT)
    ready, message = settings.provider_readiness()
    if not ready:
        print(message)
        return 2

    generated = settings.generated_bank_runtime_path(ROOT)
    bank = PracticeBank(writable_path=generated).load()
    service = LiveGenerationService(settings, bank, ROOT)
    maximum = args.max_questions or (5 if args.skill == "reading" else 3)

    accepted = 0
    for _ in range(max(1, args.count)):
        try:
            result = service.generate_and_store(
                skill=args.skill,
                level=args.level,
                mode=args.mode,
                topics=args.topic,
                competencies=args.competency,
                maximum_questions=maximum,
            )
            accepted += 1
            verifier = (
                f"; verifier={result.verifier_provider}/{result.verifier_model}"
                if result.verifier_provider and result.verifier_model else ""
            )
            print(
                f"Accepted and stored {result.passage.id}: {len(result.questions)} questions "
                f"via {result.provider_name}/{result.model_name}{verifier}; "
                f"provider_calls={result.request_count}; repairs={result.repair_count}"
            )
        except Exception as exc:
            print(f"Candidate quarantined; operational bank unchanged: {type(exc).__name__}: {exc}")

    print(f"Accepted {accepted}/{max(1, args.count)} bundles. Generated bank: {generated}")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
