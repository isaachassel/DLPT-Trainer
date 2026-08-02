from __future__ import annotations

import getpass
import sys
from pathlib import Path


REPO_ID = "alsubij/Multi-Language-DLPT"
ROOT = Path(__file__).resolve().parent

REQUIRED_PATHS = (
    "README.md",
    "app.py",
    "requirements.txt",
    "core/__init__.py",
    "core/session.py",
    "ui/__init__.py",
    "ui/layout.py",
    "data/starter_items.jsonl",
    "data/mandarin_starter_items.jsonl",
)

IGNORE_PATTERNS = (
    ".git/**",
    "**/__pycache__/**",
    "**/*.pyc",
    ".pytest_cache/**",
    ".venv/**",
    "backup/**",
    "*.zip",
    "UPLOAD_TO_HUGGINGFACE.bat",
    "upload_to_huggingface.py",
    "START_HERE_UPLOAD.txt",
)


def fail(message: str) -> None:
    print(f"\nERROR: {message}")
    input("\nPress Enter to close...")
    raise SystemExit(1)


def verify_local_package() -> None:
    missing = [relative for relative in REQUIRED_PATHS if not (ROOT / relative).is_file()]
    if missing:
        fail("The extracted package is incomplete. Missing: " + ", ".join(missing))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if not readme.startswith("---\n") or "sdk: gradio" not in readme[:800]:
        fail("README.md does not contain valid Hugging Face Space metadata.")

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    if "from core.config import" not in app_source or "from ui.layout import" not in app_source:
        fail("app.py is not the expected multilingual application entry point.")


def main() -> None:
    verify_local_package()

    print("\nRussian + Mandarin DLPT Space repair uploader")
    print(f"Target: https://huggingface.co/spaces/{REPO_ID}")
    print("\nThis will replace the currently corrupted repository contents with the")
    print("verified app folder. Hugging Face keeps commit history, so the prior")
    print("state remains recoverable.")

    confirmation = input("\nType REPLACE to continue: ").strip()
    if confirmation != "REPLACE":
        print("Cancelled. Nothing was uploaded.")
        return

    token = getpass.getpass("Paste a Hugging Face WRITE token (input is hidden): ").strip()
    if not token:
        fail("No token was entered.")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        fail("huggingface_hub is not installed. Run UPLOAD_TO_HUGGINGFACE.bat again.")

    try:
        api = HfApi(token=token)
        account = api.whoami()
        account_name = account.get("name", "authenticated user")
        print(f"\nAuthenticated as {account_name}. Uploading the verified folder...")
        api.upload_folder(
            folder_path=str(ROOT),
            repo_id=REPO_ID,
            repo_type="space",
            ignore_patterns=list(IGNORE_PATTERNS),
            delete_patterns="*",
            commit_message="Restore correct multilingual DLPT Space structure",
        )
    except Exception as exc:
        fail(str(exc))
    finally:
        token = ""

    print("\nUPLOAD COMPLETE")
    print(f"Open: https://huggingface.co/spaces/{REPO_ID}")
    print("Hugging Face should rebuild the Space automatically.")
    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
