"""Local vocabulary studio plus the existing adaptive assessment. Never a public server."""
import os
from pathlib import Path

os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
for key in ('AUTO_PROVISION_DATASET_BANK', 'SYNC_GENERATED_BANK_ON_STARTUP', 'SYNC_GENERATED_BANK_ON_WRITE'):
    os.environ[key] = 'false'
os.environ['GENERATION_PROVIDER'] = 'disabled'

import gradio as gr
from core.demo_hosting import is_hosted_demo
from core.study_content import StudyCatalog
from core.study_store import StudyStore
from ui.study import build_study_ui, STUDY_CSS
from ui.demo import build_app as build_assessment, CUSTOM_CSS

ROOT = Path(__file__).resolve().parent


def build_app(catalog=None, store=None):
    if is_hosted_demo():
        raise RuntimeError('The vocabulary studio is local-only. Public hosting requires a separate privacy/authentication review.')
    catalog = catalog or StudyCatalog()
    store = store or StudyStore(ROOT / 'storage/study/profiles.sqlite3')
    assessment = build_assessment()
    with gr.Blocks(title='DLPT Trainer · Vocabulary studio', analytics_enabled=False) as app:
        with gr.Tabs():
            with gr.Tab('Vocabulary study'):
                build_study_ui(catalog, store)
            with gr.Tab('Adaptive assessment'):
                assessment.render()
    app.queue(default_concurrency_limit=1, max_size=32)
    return app


def launch_kwargs(port=7864):
    return dict(server_name='127.0.0.1', server_port=port, share=False, ssr_mode=False,
                css=CUSTOM_CSS + STUDY_CSS, footer_links=[], show_error=False,
                allowed_paths=[str(ROOT / 'data/assessment/audio'), str(ROOT / 'data/study/audio')],
                blocked_paths=[str(ROOT / 'storage/study'), str(ROOT / 'storage/vocabulary'),
                               str(ROOT / '.env'), str(ROOT / '.git')])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7864)
    args = parser.parse_args()
    build_app().launch(**launch_kwargs(args.port))
