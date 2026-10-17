"""Browser-upload entry point: unpack the reviewed app bundle and run it."""
from pathlib import Path
import hashlib
import os
import runpy
import sys
import zipfile


def unpack(archive: Path) -> Path:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
    destination = archive.parent / f"_demo_{digest}"
    destination.mkdir(exist_ok=True)
    if not destination.resolve().is_relative_to(archive.parent.resolve()):
        raise ValueError("Unsafe extraction directory")
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive entry")
        bundle.extractall(destination)
    return destination


if __name__ == "__main__":
    root = unpack(Path(__file__).resolve().with_name("dlpt-demo.zip"))
    os.environ["DEMO_HOSTED"] = "true"
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.chdir(root)
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / "app.py"), run_name="__main__")
