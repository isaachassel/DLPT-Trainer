from __future__ import annotations

from pathlib import Path
import logging
import os
import sys

# Hugging Face's optional Xet downloader can create short-lived asyncio loops
# during startup. On Python 3.11/Spaces this sometimes prints harmless but alarming
# ``Invalid file descriptor: -1`` finalizer tracebacks. The standard HTTP path is
# fully adequate for these small JSONL/MP3 bank assets and is more predictable.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("DO_NOT_TRACK", "1")

# Python 3.11 + some HF/Gradio dependency combinations can emit an unraisable
# BaseEventLoop finalizer warning after a successful startup. It is not an app
# failure, but it looks like one in Space logs. Suppress only this exact benign
# finalizer; every other unraisable exception still goes to Python's default hook.
_DEFAULT_UNRAISABLE_HOOK = sys.unraisablehook

def _dlpt_unraisable_hook(args):
    exc = getattr(args, "exc_value", None)
    obj = getattr(args, "object", None)
    if isinstance(exc, ValueError) and "Invalid file descriptor: -1" in str(exc):
        name = getattr(obj, "__qualname__", "") or getattr(obj, "__name__", "")
        if "BaseEventLoop.__del__" in name:
            return
    _DEFAULT_UNRAISABLE_HOOK(args)

sys.unraisablehook = _dlpt_unraisable_hook

from core.config import get_settings
from core.demo_hosting import is_hosted_demo
# This branch is a self-contained demo: no generation, remote restore or sync.
for _demo_setting in ("AUTO_PROVISION_DATASET_BANK", "SYNC_GENERATED_BANK_ON_STARTUP", "SYNC_GENERATED_BANK_ON_WRITE"):
    os.environ[_demo_setting] = "false"
os.environ["GENERATION_PROVIDER"] = "disabled"
from ui.demo import CUSTOM_CSS, build_app

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

ROOT = Path(__file__).resolve().parent
settings = get_settings()
settings.ensure_directories(ROOT)
demo = build_app()


def launch_kwargs() -> dict:
    """Centralized, testable Hugging Face Space launch configuration."""

    preset_audio = (ROOT / "data" / "assessment" / "audio").resolve()
    runtime_audio = settings.audio_cache_runtime_path(ROOT).resolve()
    runtime_exports = settings.runtime_path(Path("storage/exports"), ROOT, "exports").resolve()
    runtime_audio.mkdir(parents=True, exist_ok=True)
    runtime_exports.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "server_name": settings.app_host,
        "server_port": settings.app_port,
        # Production users receive sanitized callback messages rather than raw
        # framework tracebacks. Local development can opt back in with
        # APP_ENV=development.
        "show_error": settings.environment.lower() != "production",
        "css": CUSTOM_CSS,
        # HF Spaces enables experimental SSR by default for Gradio 6. The Node
        # proxy can emit /graphql 405s and event-loop finalizer noise. This app
        # does not need SSR, so use the stable client-rendered path explicitly.
        "ssr_mode": False,
        "footer_links": [],
        # Serve only approved audio and the controlled runtime assets.
        "allowed_paths": [str(preset_audio), str(runtime_audio), str(runtime_exports)],
    }
    if is_hosted_demo():
        # Public demo endpoints serve recordings, never learner checkpoints or
        # exports. The local resume workflow remains available on this machine.
        kwargs["allowed_paths"] = [str(preset_audio)]
        kwargs["blocked_paths"] = [
            str(ROOT / "storage"), str(ROOT / ".env"), str(ROOT / ".git"),
            str(settings.session_runtime_path(ROOT)),
            str(settings.history_runtime_path(ROOT)), str(runtime_exports),
        ]
    return kwargs


if __name__ == "__main__":
    demo.launch(**launch_kwargs())
