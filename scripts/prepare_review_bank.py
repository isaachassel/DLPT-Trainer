"""One-time explicit migration: existing accepted != curator-approved."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.item_bank import ItemBank
from core.preset_bank import ContentItem, ContentPackage, MANIFEST, ROOT, Review, write_package


def main():
    if MANIFEST.exists():
        raise SystemExit("Manifest already exists; migration will not overwrite curator decisions")
    bank = ItemBank([ROOT / "data/starter_items.jsonl", ROOT / "data/mandarin_starter_items.jsonl"]).load()
    items = []
    for p in bank.passages.values():
        audio = bank.get_audio(p.audio_asset_id)
        digest = None
        if audio and audio.path:
            path = ROOT / audio.path
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items.append(ContentItem(id=p.id, passage=p, questions=bank.get_questions(p.id), audio=audio,
                                 audio_sha256=digest, review=Review(notes="Imported starter content. Original curator, pronunciation, ILR and reuse review undocumented. Pending explicit review.")))
    write_package(MANIFEST, ContentPackage(items=items))


if __name__ == "__main__":
    main()
