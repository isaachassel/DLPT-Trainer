from __future__ import annotations
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def logit(p: float) -> float:
    p = min(0.99, max(0.01, p))
    return math.log(p / (1 - p))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create provisional aggregate calibration summaries from exported response CSV files.")
    parser.add_argument("inputs", nargs="+", help="Response CSV exports")
    parser.add_argument("--output", default="storage/calibration_summary.json")
    args = parser.parse_args()
    by_item = defaultdict(lambda: {"correct": 0, "attempted": 0, "distractors": defaultdict(int), "modes": defaultdict(int)})
    for filename in args.inputs:
        with open(filename, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                item = by_item[row["question_id"]]
                item["attempted"] += 1
                item["correct"] += row["is_correct"].lower() in {"true", "1"}
                item["distractors"][row.get("selected_key", "")] += 1
                item["modes"][row.get("mode", "unknown")] += 1
    output = {}
    for item_id, stats in by_item.items():
        p = stats["correct"] / max(1, stats["attempted"])
        output[item_id] = {
            "attempted": stats["attempted"],
            "correct": stats["correct"],
            "p_value": p,
            "rough_rasch_difficulty": -logit(p),
            "distractor_counts": dict(stats["distractors"]),
            "mode_counts": dict(stats["modes"]),
            "warning": "Exploratory only; do not treat as calibrated until sample size and model-fit criteria are met.",
        }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(output)} item summaries to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
