"""Build an allowlisted deployment ZIP locally; never upload or publish anything."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package_files(root: Path = ROOT) -> list[Path]:
    paths = [root / name for name in ("app.py", "requirements.txt", "LICENSE")]
    for pattern in ("core/*.py", "ui/*.py", "ui/*.js", "data/schemas/*.json"):
        paths.extend(root.glob(pattern))
    # Only ship active manifest references, never retired/orphan recordings.
    bank_path = root / "data/assessment/bank.json"
    if not bank_path.is_file():
        raise ValueError("Missing or unsafe package entry: bank.json")
    for item in json.loads(bank_path.read_text(encoding="utf-8"))["items"]:
        if item.get("audio"):
            review = item.get("recording", {}).get("license_review") or {}
            if (item.get("recording", {}).get("account_tier") not in
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
            if (not asset.is_file() or review.get("audio_sha256") != item.get("audio_sha256")
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
12 questions, up to 30 minutes. Results are unvalidated practice estimates, not
official DLPT scores or reliable predictions. No runtime generation or API keys
are required. Listening recordings use licensed synthetic voices.

All active recordings were generated during a paid subscription using a
generally available model. Generation and licensing provenance is retained in
the bank and `data/assessment/audio/NOTICE.md`. No provider title attribution is
required for these recordings under the reviewed standard paid-plan terms.
The code's MIT license does not replace the audio provider's applicable terms.

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
            bundle.writestr(name, content)
            manifest.append({"path": name, "bytes": len(content),
                             "sha256": hashlib.sha256(content).hexdigest()})
        bundle.writestr("README.md", SPACE_README)
        manifest.append({"path": "README.md", "bytes": len(SPACE_README.encode()),
                         "sha256": hashlib.sha256(SPACE_README.encode()).hexdigest()})
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
