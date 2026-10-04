from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import get_settings
from core.preset_bank import PracticeBank, MANIFEST
from core.validation import answer_length_leakage_summary, answer_position_balance, bank_balance_passes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate approved bundled content plus the generated-bank overlay.")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--generated", default=None)
    args = parser.parse_args()
    settings = get_settings()
    manifest = Path(args.manifest) if args.manifest else MANIFEST
    generated = Path(args.generated) if args.generated else settings.generated_bank_runtime_path(ROOT)
    bank = PracticeBank(writable_path=generated, manifest=manifest).load()
    errors = bank.validate_operational_bank() + bank.load_warnings
    print(f"Approved manifest: {manifest}")
    print(f"Generated overlay: {generated}")
    print(f"Passages: {len(bank.passages)}")
    print(f"Questions: {len(bank.questions)}")
    print(f"Audio assets: {len(bank.audio_assets)}")
    print(f"Answer positions: {answer_position_balance(bank.questions.values())}")
    for language in ("ru", "zh-CN"):
        for skill in ("reading", "listening"):
            passages = bank.active_passages(skill, language)
            questions = [question for passage in passages for question in bank.get_questions(passage.id)]
            leakage = answer_length_leakage_summary(questions)
            print(
                f"{language} {skill}: {len(passages)} passages / {len(questions)} questions; "
                f"longest-choice expected score={leakage['longest_strategy_expected_rate']:.1%}; "
                f"material flags={leakage['materially_flagged']}"
            )
    if not bank_balance_passes(bank.questions.values(), tolerance=max(4, len(bank.questions) // 8)):
        errors.append("Answer-position distribution is outside tolerance.")
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
