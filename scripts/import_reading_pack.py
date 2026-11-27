"""Import an authentic reading pack as versioned drafts, never the active manifest."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.preset_bank import MANIFEST, read_package, write_package
from core.reading_import import convert_reading_pack


def import_file(source: Path, output: Path, version: int = 1):
    if output.resolve() == MANIFEST.resolve():
        raise ValueError("Import to a draft package, never the active bank")
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    package = convert_reading_pack(data, version)
    archive = output.parent / "versions" / f"v{version}" / "reading_bank.json"
    if archive.exists() and archive.read_bytes() != raw:
        raise ValueError("Source changed: increase --version; prior records are immutable")
    if output.exists():
        prior = read_package(output)
        if prior == package:
            return len(package.items)
        if version <= max(x.content_version for x in prior.items):
            raise ValueError("Increase --version to replace an existing draft; retain prior review")
        old_archive = output.parent / "versions" / f"v{max(x.content_version for x in prior.items)}" / "package.json"
        if not old_archive.exists():
            write_package(old_archive, prior)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(raw)
    write_package(archive.parent / "package.json", package)
    write_package(output, package)
    return len(package.items)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--version", type=int, default=1)
    args = p.parse_args()
    count = import_file(args.source, args.output, args.version)
    print(f"{count} drafts imported; no approvals, generation calls or production bank changes.")
