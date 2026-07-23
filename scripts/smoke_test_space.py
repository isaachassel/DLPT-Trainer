from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import get_settings
from core.item_bank import ItemBank
from ui.layout import build_app


def main() -> int:
    settings = get_settings()
    bank = ItemBank(
        [settings.starter_bank_runtime_path(ROOT), settings.generated_bank_runtime_path(ROOT)],
        writable_path=settings.generated_bank_runtime_path(ROOT),
    ).load()
    errors = bank.validate_operational_bank()
    if errors:
        print("Item bank failed:", errors)
        return 1
    app = build_app()
    config = app.get_config_file()
    if not config or "components" not in config:
        print("Gradio config was not generated.")
        return 1
    ready, provider_message = settings.provider_readiness()
    print(
        f"Smoke test passed: {len(bank.passages)} passages, {len(bank.questions)} questions, "
        f"{len(config['components'])} UI components. Live generation ready={ready}: {provider_message}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
