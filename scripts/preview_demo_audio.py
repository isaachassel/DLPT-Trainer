"""Local browser QA: shortest real approved audio, with production event wiring."""
import os
import sys
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for key in ('AUTO_PROVISION_DATASET_BANK', 'SYNC_GENERATED_BANK_ON_STARTUP', 'SYNC_GENERATED_BANK_ON_WRITE'):
    os.environ[key] = 'false'
os.environ['GENERATION_PROVIDER'] = 'disabled'
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'

from ui import demo
from core.session import activate_bundle
from core.storage import LocalStorage


def main():
    start = demo.start_demo
    def short_audio(language, skill='Listening'):
        result = start(language, 'Listening')
        state = result[0]
        state.selected_skills = ['listening']
        state.active_skill_index = 0
        bank = demo.cb.PRESET_BANK
        passage = next(p for p in bank.active_passages('listening', state.language) if p.target_ilr == '0')
        bundle = activate_bundle(state, passage, bank.get_questions(passage.id))
        return demo.present(demo.cb._test_render(state, bundle))
    demo.start_demo = short_audio
    submit = demo.submit_demo
    def next_short_audio(state, bundle, nonce, *answers):
        previous = state.current_passage_id
        result = submit(state, bundle, nonce, *answers)
        if state.status == 'active' and state.current_passage_id != previous:
            bank = demo.cb.PRESET_BANK
            available = [p for p in bank.active_passages('listening', state.language)
                         if p.target_ilr == '0' and p.id not in state.completed_passage_ids]
            if available:
                passage = available[0]
                new_bundle = activate_bundle(state, passage, bank.get_questions(passage.id))
                return demo.present(demo.cb._test_render(state, new_bundle))
        return result
    demo.submit_demo = next_short_audio
    with tempfile.TemporaryDirectory(prefix='dlpt-demo-qa-') as folder:
        demo.cb.STORAGE = LocalStorage(Path(folder) / 'sessions', Path(folder) / 'history')
        demo.cb.EXPORT_DIR = Path(folder) / 'exports'
        demo.build_app().launch(server_name='127.0.0.1', server_port=7861, ssr_mode=False,
                                css=demo.CUSTOM_CSS, footer_links=[],
                                allowed_paths=[str(ROOT / 'data/assessment/audio')])


if __name__ == '__main__':
    main()
