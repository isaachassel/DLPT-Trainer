from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {".pytest_cache", "__pycache__"}
EXCLUDED_FILES = {"MANIFEST.sha256"}
RELEASE_STORAGE_FILES = {
    "storage/cache/audio/.gitkeep",
    "storage/exports/.gitkeep",
    "storage/history/.gitkeep",
    "storage/item_bank/.gitkeep",
    "storage/item_bank/generated_items.jsonl",
    "storage/item_bank/generated_items.meta.json",
    "storage/quarantine/.gitkeep",
}


def main() -> None:
    paths = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] == "storage" and relative.as_posix() not in RELEASE_STORAGE_FILES:
            continue
        if path.name in EXCLUDED_FILES or path.suffix == ".pyc":
            continue
        paths.append(path)
    lines = []
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{path.relative_to(ROOT).as_posix()}")
    (ROOT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} release checksums.")


if __name__ == "__main__":
    main()
