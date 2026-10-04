"""Local trusted curator only; never registered as a web callback."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.preset_bank import (ContentPackage, MANIFEST, ROOT, Review, local_asset, read_package,
                              validate_item, write_package)


def promote(package_path, item_id, reviewer, notes, reuse_attested, manifest=MANIFEST, root=ROOT, reject=False):
    if not reviewer.strip() or not notes.strip() or (not reject and not reuse_attested):
        raise ValueError("Named reviewer, review notes and explicit reuse attestation are required")
    package = read_package(package_path)
    item = next((x.model_copy(deep=True) for x in package.items if x.id == item_id), None)
    if not item:
        raise ValueError("Item ID not found")
    base = root if package_path.resolve() == manifest.resolve() else package_path.parent
    if not reject:
        validate_item(item, base)
    item.review = Review(status="rejected" if reject else "approved", reviewer=reviewer,
                         notes=notes, reviewed_at=datetime.now(timezone.utc).isoformat(), reuse_attested=reuse_attested)
    shared = read_package(manifest) if manifest.exists() else ContentPackage()
    prior = next((x for x in shared.items if x.id == item.id), None)
    if prior and prior.review.status == "approved" and not reject:
        if item.content_version <= prior.content_version:
            raise ValueError("Updating approved content requires a higher content_version and fresh review")
    source = destination = None
    if item.audio and not reject:
        source = local_asset(base, item.audio.path)
        relative = f"data/assessment/audio/{item.id}-{item.audio_sha256}.mp3"
        item.audio.path = relative
        item.audio.validated = True
        destination = root / relative
    merged = ContentPackage(items=[x for x in shared.items if x.id != item.id] + [item])
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    write_package(manifest, merged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "approve", "reject"])
    parser.add_argument("--package", type=Path, default=MANIFEST)
    parser.add_argument("--item")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--attest-reuse-rights", action="store_true")
    args = parser.parse_args()
    if args.action == "validate":
        package = read_package(args.package)
        base = ROOT if args.package.resolve() == MANIFEST.resolve() else args.package.parent
        failed = 0
        for item in package.items:
            try:
                validate_item(item, base)
                print(f"{item.id}: {item.review.status}; structural checks pass (not a human review)")
            except ValueError as exc:
                failed += 1
                print(f"{item.id}: {item.review.status}; {exc}")
        raise SystemExit(1 if failed else 0)
    promote(args.package, args.item, args.reviewer, args.notes, args.attest_reuse_rights, reject=args.action == "reject")
    print("Curator decision saved locally. Restart the app to load the reviewed snapshot. No push performed.")


if __name__ == "__main__":
    main()
