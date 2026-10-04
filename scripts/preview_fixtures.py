"""Explicit local-only QA app. Never deploy: fake provider and TEST-only review decisions."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key, value in {"GENERATION_PROVIDER": "disabled", "AUTO_PROVISION_DATASET_BANK": "false",
                   "SYNC_GENERATED_BANK_ON_STARTUP": "false", "SYNC_GENERATED_BANK_ON_WRITE": "false",
                   "GRADIO_ANALYTICS_ENABLED": "False"}.items():
    os.environ[key] = value


def main():
    from core.content_workshop import Workshop
    from core.preset_bank import PresetBank, MANIFEST, ROOT, Review, read_package, write_package
    import ui.callbacks as cb
    import ui.workshop as ui

    class MockProvider:
        provider_name = "NONPRODUCTION MOCK — unrelated fixture audio, never ElevenLabs output"
        def __init__(self, key):
            pass

        def catalog(self):
            return {"account": {"tier": "NONPRODUCTION MOCK — NO CHARGES"},
                    "models": [{"model_id": "mock-dialogue-no-provider"}],
                    "voices": [{"name": "TEST voice A", "voice_id": "mock-a"},
                               {"name": "TEST voice B", "voice_id": "mock-b"}]}

        def dialogue(self, turns, voices, model):
            # Existing fixture MP3 for playback only; it does NOT speak the new draft.
            return (ROOT / "tests/fixtures/legacy/audio/l001.mp3").read_bytes()

    class MockWorkshop(Workshop):
        def configure(self, key, client_factory=MockProvider):
            return super().configure("NONSECRET MOCK", MockProvider)

    ui.Workshop = MockWorkshop
    with tempfile.TemporaryDirectory(prefix="dlpt-qa-") as directory:
        manifest = Path(directory) / "fixture-bank.json"
        package = read_package(MANIFEST)
        for item in package.items:
            item.review = Review(status="approved", reviewer="NONPRODUCTION TEST FIXTURE",
                                 reviewed_at="2026-10-03", reuse_attested=True)
        write_package(manifest, package)
        cb.PRESET_BANK = PresetBank(manifest, ROOT).load()
        from core.storage import LocalStorage
        cb.STORAGE = LocalStorage(Path(directory) / "sessions", Path(directory) / "history")
        cb.EXPORT_DIR = Path(directory) / "exports"
        import gradio as gr
        from ui.layout import build_app, CUSTOM_CSS
        app = build_app()
        with app:
            gr.Markdown("# NONPRODUCTION FIXTURE PREVIEW\nNo provider calls or charges. Review decisions are TEST ONLY. "
                        "Mock audio reuses an existing unrelated fixture and does NOT speak the new dialogue. Do not export or curate mock output.")
        app.launch(server_name="127.0.0.1", server_port=7861, ssr_mode=False, css=CUSTOM_CSS,
                   allowed_paths=[str(ROOT / "tests/fixtures/legacy/audio"), str(cb.EXPORT_DIR)])


if __name__ == "__main__":
    main()
