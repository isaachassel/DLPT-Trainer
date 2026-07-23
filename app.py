from __future__ import annotations

from core.config import get_settings
from ui.layout import CUSTOM_CSS, build_app

settings = get_settings()
demo = build_app()

if __name__ == "__main__":
    demo.launch(server_name=settings.app_host, server_port=settings.app_port, show_error=True, css=CUSTOM_CSS)
