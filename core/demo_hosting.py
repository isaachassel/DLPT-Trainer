"""Hosting safeguards for the demo, without changing the local preview workflow."""
import os


def is_hosted_demo() -> bool:
    return bool(os.getenv("SPACE_ID")) or os.getenv("DEMO_HOSTED", "").lower() in {"1", "true", "yes"}
