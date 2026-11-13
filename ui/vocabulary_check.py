"""Multi-word passage check, with server-only keys and a review handoff."""
from html import escape
import gradio as gr
from core.vocabulary_check import UNKNOWN


def report_html(state):
    if state.get('status') != 'complete':
        return ''
    results = [r for p in state['completed'] for r in p['results']]
    focus = [r for r in results if not r['correct'] or r['guessed']]
    reasons = {'planned_length': 'Planned passages completed.',
               'content_exhausted': 'No more matching passages are available in this pilot bank.',
               'stopped_by_learner': 'You ended the check early.'}
    if not results:
        return '<div class="study-card"><h2>No words assessed yet</h2><p>The check ended before any answers were submitted. Your vocabulary evidence has not changed.</p></div>'
    if state.get('collection') == 'ales':
        # One word per row. Any missed/guessed observation in this test needs work.
        grouped = {}
        for r in results:
            previous = grouped.get(r['word_id'])
            if previous is None or not r['correct'] or r['guessed']:
                grouped[r['word_id']] = r
        recognized = [r for r in grouped.values() if r['correct'] and not r['guessed']]
        review = [r for r in grouped.values() if not r['correct'] or r['guessed']]
        def section(title, entries):
            rows = ''.join(f'<tr><td lang="ru">{escape(r["term"])}</td><td>{escape(r["meaning"])}</td>'
                f'<td>{escape(r["selected"])}</td><td>{"Guessed" if r["guessed"] else "Correct" if r["correct"] else "Missed"}</td></tr>' for r in entries)
            return (f'<h3>{title} ({len(entries)})</h3><table><thead><tr><th>ALES word</th><th>Meaning here</th>'
                f'<th>Your answer</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table>' if entries else f'<h3>{title} (0)</h3><p>None in this check.</p>')
        details = ''.join(f'<li><strong>{escape(r["prompt"] or r["term"])}</strong><p>{escape(r["explanation"] or r["meaning"])}</p>'
                         f'<p lang="ru">{escape(r["evidence"] or "")}</p></li>' for r in results)
        return (f'<div class="study-card"><h2>Your ALES study plan</h2><p>{escape(reasons.get(state.get("end_reason"), "Check complete."))}</p>'
            f'<p><strong>{len(grouped)} distinct word senses checked</strong> in {len(state["completed"])} '
            f'{"passage" if len(state["completed"]) == 1 else "passages"}. '
            f'{state["glossary_count"] - len(grouped)} glossary entries were not tested in this check. '
            f'The current {state["skill"]} passage bank covers {state["covered_count"]} of {state["glossary_count"]} entries.</p>'
            '<p>Saved to your profile. Review missed and guessed words next. Correct recognition in one context is encouraging; '
            'it does not establish mastery. Reading and listening progress are separate.</p>'
            + section('Correctly recognized without guessing', recognized) + section('Words to work on again', review)
            + f'<details><summary>Question explanations</summary><ol>{details}</ol></details></div>')
    correct = sum(r['correct'] for r in results)
    rows = ''.join(f'<tr><td lang="ru">{escape(r["term"])}</td><td>{escape(r["meaning"])}</td>'
                   f'<td>{escape(r["selected"])}</td><td>{"Review next" if not r["correct"] or r["guessed"] else "Correct; confirm later"}</td></tr>' for r in results)
    return (f'<div class="study-card"><h2>Your vocabulary review plan</h2><p>{correct} of {len(results)} meanings correct. '
            f'<strong>{len(focus)} missed or guessed words to focus on.</strong></p>'
            f'<p>{escape(reasons.get(state.get("end_reason"), "Check complete."))}</p>'
            '<p>Your next reviews prioritize these weaker words. Correct answers are promising, but one passage does not establish mastery. '
            'Untested words remain unassessed. This check does not estimate your DLPT level.</p>'
            '<table><thead><tr><th>Word</th><th>Meaning here</th><th>Your answer</th><th>Next step</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


class CheckUI:
    def __init__(self):
        self.identifier, self.nonce = gr.State(''), gr.State('')
        with gr.Accordion('Start with a passage vocabulary check', open=True):
            gr.Markdown('Read or hear a longer passage and answer up to six word-meaning questions. '
                        'The next passage adapts to your answers. At the end, review the words you missed or guessed. '
                        'Choose the skill and course filters above. Answers stay hidden until the check ends.')
            with gr.Row():
                self.length = gr.Dropdown([2, 3, 4, 5, 10, 15], value=3, label='Passages to check')
                self.begin = gr.Button('Start vocabulary check', variant='primary')
        with gr.Column(visible=False) as self.panel:
            self.heading = gr.Markdown()
            with gr.Row(elem_classes=['vocab-check-panels']):
                with gr.Column(elem_classes=['vocab-check-pane']):
                    self.passage = gr.HTML()
                    self.audio = gr.Audio(interactive=False, visible=False, buttons=[], label='Passage recording')
                with gr.Column(elem_classes=['vocab-check-pane']):
                    self.slots, self.choices, self.guesses = [], [], []
                    for n in range(6):
                        # Gradio's auto-grouped form can retain an empty Radio when
                        # its choices and visibility change together (e.g. 3 -> 2).
                        # Hide the whole slot instead of toggling individual inputs.
                        with gr.Column(visible=False, min_width=0, elem_classes=['vocab-question-slot']) as slot:
                            self.choices.append(gr.Radio(choices=[UNKNOWN], label=f'Word {n + 1}', interactive=True))
                            self.guesses.append(gr.Checkbox(False, label='That was a guess'))
                        self.slots.append(slot)
            with gr.Row():
                self.submit = gr.Button('Submit passage answers', variant='primary')
                self.stop = gr.Button('End check and see review plan')
        self.report = gr.HTML(visible=False)
        self.focus = gr.Button('Review my weaker words', visible=False, variant='primary')
        self.outputs = [self.identifier, self.nonce, self.panel, self.heading, self.passage, self.audio,
                        *[c for triple in zip(self.slots, self.choices, self.guesses) for c in triple], self.report, self.focus]

    def present(self, state):
        active = state.get('status') == 'active'
        current = state.get('current') if active else None
        values = [state.get('id', ''), current['nonce'] if current else '', gr.update(visible=active)]
        if current:
            values += [f'### Passage {len(state["completed"]) + 1} of up to {state["maximum"]} · {state["skill"].title()} · {len(current["targets"])} words\n\n'
                       + current['title'] + '\n\nAnswer using the passage. Mark a guess so it can be reviewed. Listening allows replays for this study check.']
            text = escape(current['text']) if state['skill'] == 'reading' else 'Listen to the conversation. The transcript will appear with the review plan.'
            values += [f'<div class="study-card"><div class="russian" lang="ru">{text}</div></div>',
                       gr.update(value=current['audio_path'] if state['skill'] == 'listening' else None,
                                 visible=state['skill'] == 'listening')]
        else:
            values += ['', '', gr.update(value=None, visible=False)]
        for n in range(6):
            target = current['targets'][n] if current and n < len(current['targets']) else None
            values += [gr.update(visible=bool(target)),
                       gr.update(choices=target['options'] + [UNKNOWN] if target else [], value=None,
                                 label=f'{n + 1}. ' + target.get('prompt', f'What does “{target["target"]}” mean here?') if target else '',
                                 visible=bool(target), interactive=bool(target)), gr.update(value=False, interactive=bool(target))]
        report = report_html(state) if state.get('status') == 'complete' else ''
        if report and state['skill'] == 'listening':
            for passage in state['completed']:
                report += f'<details class="study-card"><summary>Transcript: {escape(passage["title"])}</summary><p>{escape(passage["text"])}</p></details>'
        has_focus = any(not r['correct'] or r['guessed'] for p in state.get('completed', []) for r in p['results'])
        values += [gr.update(value=report, visible=bool(report)), gr.update(visible=bool(report) and has_focus)]
        return values

    def bind(self, token, filters, store, catalog, safe, common, review_outputs, view, advance, dashboard, presenter):
        def begin(t, length, *f):
            identifier = store.start_check(t, catalog, list(f), int(length))
            store.abandon(t)
            return [*self.present(store.check_state(t, identifier)), *view(t, {})]
        self.begin.click(safe(begin), [token, self.length, *filters], [*self.outputs, *review_outputs], **common)

        def submit(t, identifier, nonce, *responses):
            state = store.check_state(t, identifier)
            # Snapshot question count is bound to submitted nonce, including idempotent retry.
            passage = next((p for p in state['completed'] if p['nonce'] == nonce), state.get('current'))
            count = len(passage['targets']) if passage else 0
            state = store.submit_check(t, identifier, nonce, list(responses[:6])[:count], list(responses[6:])[:count])
            return [*self.present(state), presenter.dashboard(t, *state['filters'])]
        self.submit.click(safe(submit), [token, self.identifier, self.nonce, *self.choices, *self.guesses],
                          [*self.outputs, dashboard], **common)
        def stop(t, i):
            state = store.cancel_check(t, i)
            return [*self.present(state), presenter.dashboard(t, *state['filters'])]
        self.stop.click(safe(stop), [token, self.identifier], [*self.outputs, dashboard], **common)

        def focus(t, identifier):
            state = store.check_state(t, identifier)
            if state['status'] != 'complete':
                raise ValueError('Finish the vocabulary check first.')
            return [*advance(t, dict(nonce=None, seen=[], reviewed=0, filters=state['filters'], focus_only=True)),
                    gr.update(value='', visible=False), gr.update(visible=False)]
        self.focus.click(safe(focus), [token, self.identifier], [*review_outputs, self.report, self.focus], **common)
        return self.outputs
