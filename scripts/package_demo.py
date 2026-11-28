"""Build an allowlisted deployment ZIP locally; never upload or publish anything."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate_authentic_audio(item, root):
    """Separate release path for attributed radio excerpts, never a TTS exception."""
    from core.preset_bank import ContentItem, validate_item
    from core.reading_import import public_url
    native = ContentItem.model_validate(item)
    p, audio = native.passage, native.audio
    if (native.review.status != 'approved' or not native.review.reuse_attested or
            not audio or audio.synthetic_tts or audio.source_type != 'authentic/open-licensed' or
            p.source_type != 'authentic/open-licensed' or native.recording.provider != 'authentic radio'):
        raise ValueError('Authentic audio requires explicit named curator approval and reuse attestation')
    provenance = p.provenance
    required = ('source_author', 'source_publisher', 'source_original_url', 'audio_license',
                'audio_license_url', 'caption_author', 'caption_source_url', 'caption_license',
                'caption_license_url', 'selection', 'modifications')
    if any(not provenance.get(k) for k in required):
        raise ValueError('Authentic audio and caption attribution must be complete')
    if (audio.license != 'CC BY 3.0' or provenance['audio_license'] != audio.license or
            provenance['audio_license_url'] != 'https://creativecommons.org/licenses/by/3.0/' or
            provenance['caption_license'] != 'CC BY-SA 4.0' or
            provenance['caption_license_url'] != 'https://creativecommons.org/licenses/by-sa/4.0/' or
            any(not public_url(provenance[k]) for k in required if k.endswith('_url'))):
        raise ValueError('Unsupported or inconsistent authentic source licensing; review release policy')
    if audio.content_hash != native.audio_sha256:
        raise ValueError('Authentic recording checksum review required')
    validate_item(native, root)


def package_files(root: Path = ROOT) -> list[Path]:
    paths = [root / name for name in ("app.py", "requirements.txt", "LICENSE")]
    for pattern in ("core/*.py", "ui/*.py", "ui/*.js", "data/schemas/*.json"):
        paths.extend(root.glob(pattern))
    # Only ship active manifest references, never retired/orphan recordings.
    bank_path = root / "data/assessment/bank.json"
    if not bank_path.is_file():
        raise ValueError("Missing or unsafe package entry: bank.json")
    for item in json.loads(bank_path.read_text(encoding="utf-8"))["items"]:
        if item.get("review", {}).get("status") != "approved":
            continue
        if item.get("audio"):
            authentic = item['audio'].get('source_type') == 'authentic/open-licensed'
            if authentic:
                validate_authentic_audio(item, root)
            review = item.get("recording", {}).get("license_review") or {}
            if not authentic and (item.get("recording", {}).get("account_tier") not in
                    {"starter", "creator", "pro", "scale", "business", "enterprise"}
                    or review.get("commercial_use") is not True
                    or review.get("attribution_required") is not False
                    or review.get("model_status") != "generally_available"):
                raise ValueError(f"Audio license review required: {item.get('id', 'unknown')}")
            name = item["audio"]["path"]
            asset = root / name
            audio_root = (root / "data/assessment/audio").resolve()
            if (Path(name).is_absolute() or not asset.resolve().is_relative_to(audio_root)
                    or asset.suffix.lower() != ".mp3"):
                raise ValueError("Missing or unsafe package entry: audio path")
            if (not asset.is_file() or (not authentic and review.get("audio_sha256") != item.get("audio_sha256"))
                    or hashlib.sha256(asset.read_bytes()).hexdigest() != item.get("audio_sha256")):
                raise ValueError(f"Audio checksum review required: {item.get('id', 'unknown')}")
            paths.append(asset)
    paths += [root / "data/assessment/bank.json", root / "data/assessment/audio/NOTICE.md",
              root / "data/assessment/audio_license_audit.json"]
    # Refuse symlinks/junction escapes, including those at an ancestor directory.
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Missing or unsafe package entry: {path.name}")
    return sorted(set(paths))


SPACE_README = '''---
title: "Language Test"
emoji: 🎧
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "6.5.1"
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
---

# Language Test

Independent Russian and Mandarin reading/listening practice. One skill per test,
About 12 questions, up to 30 minutes; authentic passage question groups stay together. Results are unvalidated practice estimates, not
official DLPT scores or reliable predictions. No runtime generation or API keys
are required. The bank supports reviewed synthetic recordings and licensed authentic excerpts.

Choose Preparation (start at Level 1+) or Advanced practice (start at Level 2).
Both adapt up or down and use the same initial ability estimate; your answers
determine the practice result.

Synthetic recordings must pass the paid-plan, generally-available-model release
checks. Their provenance is retained in the bank and `data/assessment/audio/NOTICE.md`.
Authentic excerpts require separate curator approval and source attribution.
The completed assessment credits the speakers, broadcaster, audio license and
separate caption license. Approved source credits are also preserved in the
server package's `SOURCE_CREDITS.html`. The code's MIT license does not replace
the media or caption licenses; CC BY-SA captions retain their license.

On Spaces, saved-report resume links are disabled and learner storage/export
directories are blocked from file serving. Answers are saved on the server for
session handling; ordinary Space disk storage may be lost on restart. There are
no learner accounts or durable learner-history guarantees in this demo.
'''


def build_package(root: Path = ROOT) -> Path:
    files = package_files(root)
    output = root / "storage/exports/deployment"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "dlpt-demo.zip"
    manifest = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            content = path.read_bytes()
            name = path.relative_to(root).as_posix()
            if name == "data/assessment/bank.json":
                bank = json.loads(content)
                bank["items"] = [{k: v for k, v in item.items() if k != "authoring_record"}
                                 for item in bank["items"] if item.get("review", {}).get("status") == "approved"]
                content = json.dumps(bank, ensure_ascii=False, indent=2).encode("utf-8")
            bundle.writestr(name, content)
            manifest.append({"path": name, "bytes": len(content),
                             "sha256": hashlib.sha256(content).hexdigest()})
        bundle.writestr("README.md", SPACE_README)
        manifest.append({"path": "README.md", "bytes": len(SPACE_README.encode()),
                         "sha256": hashlib.sha256(SPACE_README.encode()).hexdigest()})
        from core.preset_bank import read_package
        from core.source_credits import credits_html, source_snapshot
        credits = {i.id: source_snapshot(i.passage) for i in read_package(root / 'data/assessment/bank.json').items
                   if i.review.status == 'approved' and i.passage.source_type != 'synthetic'}
        notice = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Source credits</title><body>' +
                  (credits_html(credits) or '<p>No authentic excerpts in this deployment.</p>') + '</body></html>').encode('utf-8')
        bundle.writestr('SOURCE_CREDITS.html', notice)
        manifest.append({'path': 'SOURCE_CREDITS.html', 'bytes': len(notice), 'sha256': hashlib.sha256(notice).hexdigest()})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Six flat files can be uploaded using the standard browser file chooser,
    # preserving nested module/audio paths inside the reviewed archive.
    upload = output / "browser-upload"
    upload.mkdir(exist_ok=True)
    shutil.copyfile(archive, upload / archive.name)
    for name in ("requirements.txt", "LICENSE"):
        shutil.copyfile(root / name, upload / name)
    shutil.copyfile(root / "scripts/launch_space.py", upload / "launch_space.py")
    shutil.copyfile(root / "data/assessment/audio/NOTICE.md", upload / "AUDIO_NOTICE.md")
    (upload / "README.md").write_text(
        SPACE_README.replace("app_file: app.py", "app_file: launch_space.py")
        .replace("`data/assessment/audio/NOTICE.md`", "`AUDIO_NOTICE.md`"), encoding="utf-8")
    return archive


if __name__ == "__main__":
    print(build_package())
