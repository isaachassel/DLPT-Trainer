from __future__ import annotations

from pathlib import Path
import logging
import os

from core.config import get_settings
from ui.layout import CUSTOM_CSS, build_app

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

    starter_audio = (ROOT / "data" / "audio").resolve()
    runtime_audio = settings.audio_cache_runtime_path(ROOT).resolve()
    runtime_exports = settings.runtime_path(Path("storage/exports"), ROOT, "exports").resolve()
    starter_audio.mkdir(parents=True, exist_ok=True)
    runtime_audio.mkdir(parents=True, exist_ok=True)
    runtime_exports.mkdir(parents=True, exist_ok=True)
    return {
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
        # Serve only validated starter audio and the controlled TTS cache.
        "allowed_paths": [str(starter_audio), str(runtime_audio), str(runtime_exports)],
    }


if __name__ == "__main__":
    demo.launch(**launch_kwargs())
