"""Local instructor preview of teacher-review drafts; never a public diagnostic."""
import argparse
from html import escape
import os
from pathlib import Path
import sys

os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gradio as gr
from core.config import get_settings
from core.preset_bank import ROOT, read_package
from core.source_credits import credits_html, source_snapshot
from core.storage import LocalStorage
from ui.components import answer_radio

DEFAULT_PACKAGE = ROOT / "data/content_packs/ru-authentic-reading-pilot-01/package.json"


def preview_score(item, answers):
    if len(answers) != len(item.questions) or any(a not in q.choices for q, a in zip(item.questions, answers)):
        raise ValueError("Choose an answer for every question before finishing the preview.")
    correct = sum(a == q.correct_key for q, a in zip(item.questions, answers))
    missed = sorted({q.answer_position_metadata.get("source_skill", q.question_type).replace("_", " ")
                     for q, a in zip(item.questions, answers) if a != q.correct_key})
    parts = [f'<h2>Preview complete · {correct} of {len(answers)} correct</h2>',
             '<p>This is a teacher-review draft. No proficiency level is estimated and no diagnostic result is saved.</p>',
             '<p>Skills to review: ' + escape(', '.join(missed) if missed else 'None missed in this passage') + '</p>']
    for i, q in enumerate(item.questions, 1):
        original = item.authoring_record["questions"][i - 1]
        parts += [f'<h3>{i}. {escape(q.stem_en)}</h3>',
                  f'<p>Correct answer: {escape(q.correct_key)}. {escape(q.choices[q.correct_key])}</p>',
                  f'<p>{escape(q.rationale_en)}</p>']
        for evidence in original["evidence"]:
            parts.append(f'<p>Evidence ({escape(evidence["paragraph_id"])}): {escape(evidence["quote_ru"])}</p>')
        parts.append('<details><summary>Distractor review</summary>')
        parts.extend(f'<p>{escape(o["id"])}: {escape(o["rationale_en"])}</p>' for o in original["options"])
        parts.append('</details>')
    parts += ['<details><summary>Instructor review notes</summary>',
              f'<p>Suggested instructional level: {escape(item.passage.target_ilr)} (uncalibrated).</p>',
              f'<p>{escape(item.passage.provenance["difficulty_rationale"])}</p>',
              f'<p>{escape(item.review.notes)}</p></details>',
              credits_html({item.id: source_snapshot(item.passage)})]
    return ''.join(parts)


def build_preview(package_path=DEFAULT_PACKAGE):
    package = read_package(package_path)
    items = {item.id: item for item in package.items}
    settings = get_settings()
    storage = LocalStorage(settings.session_runtime_path(ROOT), settings.history_runtime_path(ROOT))

    def start(item_id, profile):
        item = items[item_id]
        if profile.strip():
            history = storage.load_history(f"{profile.strip()}__ru")
            history.seen_family_ids = sorted(set(history.seen_family_ids) | {item.passage.family_id})
            storage.save_history(history)
        updates = []
        for i in range(5):
            q = item.questions[i] if i < len(item.questions) else None
            updates.append(gr.update(visible=q is not None, label=f'{i+1}. {q.stem_en}' if q else '',
                choices=[(f'{k}. {v}', k) for k, v in q.choices.items()] if q else [], value=None))
        return [item_id, gr.update(value=f'### Reading passage\n\nPublished: {item.passage.provenance["publication_date"]}'
                f'\n\n{item.passage.orientation_en}\n\n{item.passage.passage_ru}'), *updates,
                gr.update(value='', visible=False), gr.update(visible=True)]

    def finish(item_id, *answers):
        if item_id not in items:
            raise gr.Error('Open a passage first.')
        item = items[item_id]
        try:
            report = preview_score(item, answers[:len(item.questions)])
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc
        return gr.update(value=report, visible=True)

    with gr.Blocks(title='Authentic reading · Instructor preview', analytics_enabled=False) as app:
        gr.Markdown('# Authentic Russian reading\n\n**Instructor preview · six teacher-review drafts.** '
                    'These are not active diagnostic items. Finish a passage to see the answer key, source credits and review notes.')
        selected = gr.State()
        with gr.Row():
            choice = gr.Dropdown([(f'Reading passage {n} · {item.passage.provenance["publication_date"]}', item.id)
                                 for n, item in enumerate(package.items, 1)], value=package.items[0].id, label='Choose a passage')
            profile = gr.Textbox(label='Optional local profile ID', info='Use the same ID in a local diagnostic to exclude these families. '
                                'The anonymous hosted demo cannot identify preview readers across devices.')
        begin = gr.Button('Open passage', variant='primary')
        with gr.Row():
            passage = gr.Markdown('Open a passage to begin.')
            with gr.Column():
                answers = [answer_radio(label=f'Question {i+1}', visible=False) for i in range(5)]
        finish_button = gr.Button('Finish preview and review', visible=False, variant='primary')
        report = gr.HTML(visible=False)
        begin.click(start, [choice, profile], [selected, passage, *answers, report, finish_button], api_visibility='private')
        finish_button.click(finish, [selected, *answers], report, api_visibility='private')
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--port', type=int, default=7866)
    args = parser.parse_args()
    build_preview(args.package).launch(server_name='127.0.0.1', server_port=args.port, share=False,
        blocked_paths=[str(ROOT / 'data'), str(ROOT / 'storage'), str(ROOT / '.env'), str(ROOT / '.git')],
        footer_links=[], ssr_mode=False)
