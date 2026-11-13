"""Two-question competency practice alongside the existing word-review workflow."""
from html import escape
import gradio as gr

from core.lesson_study import CATEGORIES, LessonCatalog, UNKNOWN, recommendation


def report_html(state):
    if state.get('status') != 'complete':
        return ''
    m = state['mapping']
    label = recommendation(state['results'])
    if not m['lesson']:
        label = label.replace('this lesson', 'this topic')
    lesson = m['lesson']
    reference = lesson['resource'] if lesson else 'Course lesson mapping pending. Use the review guidance below.'
    details = ''.join(f'<li><strong>{escape(q["prompt"])}</strong><br>Your answer: {escape(r["selected"])}'
                      f'{" (marked as a guess)" if r["guessed"] else ""}<br>Answer: {escape(q["answer"])}'
                      f'<br>{escape(q["explanation"])}<br><span lang="ru">{escape(q["evidence"])}</span></li>'
                      for q, r in zip(m['questions'], state['results']))
    transcript = (f'<details><summary>Transcript</summary><p style="white-space:pre-wrap" lang="ru">{escape(m["text"])}</p></details>'
                  if state['skill'] == 'listening' else '')
    return (f'<div class="study-card"><h2>{escape(label)}</h2><p>{escape(CATEGORIES[m["category"]])}: '
            f'{escape(m["objective"])}</p><p>{escape(m["review_guidance"])}</p><p>{escape(reference)}</p>'
            '<p>Based on two questions from one passage. This is provisional practice guidance, not mastery or a DLPT score. '
            'A wrong answer does not by itself explain why it was missed.</p>'
            f'<details><summary>Answers and explanations</summary><ol>{details}</ol></details>{transcript}</div>')


def history_rows(store, token, skill):
    if not token:
        return []
    rows = []
    for state in store.lesson_history(token, skill):
        m = state['mapping']
        label = recommendation(state['results'])
        if not m['lesson']:
            label = label.replace('this lesson', 'this topic')
        rows.append([m['lesson']['lesson'] if m['lesson'] else 'Lesson mapping pending',
                     CATEGORIES[m['category']], m['title'], label])
    return rows


def present(state):
    active = state.get('status') == 'active'
    m = state.get('mapping')
    heading, body, path = '', '', None
    if active:
        heading = f'### {m["title"]}\n\n{CATEGORIES[m["category"]]} · {m["objective"]}'
        body = (escape(m['text']) if state['skill'] == 'reading'
                else 'Listen to the conversation. The transcript stays hidden until you submit both answers.')
        body = f'<div class="study-card"><div class="russian" lang="ru">{body}</div></div>'
        path = m['audio_path'] if state['skill'] == 'listening' else None
    outputs = [state.get('id', ''), gr.update(visible=active), heading, body,
               gr.update(value=path, visible=bool(path))]
    for n in range(2):
        q = m['questions'][n] if active else None
        outputs += [gr.update(visible=bool(q)),
                    gr.update(label=f'{n + 1}. {q["prompt"]}' if q else '',
                              choices=q['options'] + [UNKNOWN] if q else [], value=None,
                              visible=bool(q), interactive=bool(q)), gr.update(value=False)]
    report = report_html(state)
    outputs.append(gr.update(value=report, visible=bool(report)))
    return outputs


def build_lesson_ui(study, store, token, skill, module, lesson, safe, common, auth_buttons):
    if not study.passages:
        gr.Markdown('Lesson passage practice is unavailable in this vocabulary-only collection.')
        return
    catalog = LessonCatalog(study)
    with gr.Accordion('Lesson passages · Four competency categories', open=False):
        gr.Markdown('Choose what you want to practice: **Lexical** (vocabulary), **Structural** (grammar), '
                    '**Discourse** (connections and meaning across a passage), or **Sociocultural** (register and social context). '
                    'Each dialogue is mapped through two specific questions. These author-created mappings await instructor review. '
                    'Study skill and module/lesson filters above apply here. Listening allows replays for this practice activity.')
        category = gr.Dropdown([(label, key) for key, label in CATEGORIES.items()], value='lexical', label='Competency category')
        passage = gr.Dropdown([], label='Mapped dialogue', interactive=True)
        coverage = gr.Markdown()
        begin = gr.Button('Practice mapped passage', variant='primary')
        identifier = gr.State('')
        with gr.Column(visible=False) as panel:
            heading = gr.Markdown()
            with gr.Row(elem_classes=['vocab-check-panels']):
                with gr.Column(elem_classes=['vocab-check-pane']):
                    text = gr.HTML()
                    audio = gr.Audio(interactive=False, visible=False, buttons=[], label='Lesson passage recording')
                with gr.Column(elem_classes=['vocab-check-pane']):
                    answers, guesses, slots = [], [], []
                    for n in range(2):
                        # Explicit slots avoid Gradio auto-form dropping empty
                        # radios when the hidden parent first becomes visible.
                        with gr.Column(visible=False, min_width=0, elem_classes=['lesson-question-slot']) as slot:
                            answers.append(gr.Radio(choices=[UNKNOWN], label=f'Question {n + 1}', interactive=True))
                            guesses.append(gr.Checkbox(False, label='That was a guess'))
                        slots.append(slot)
            submit = gr.Button('Check passage and show study guidance', variant='primary')
        report = gr.HTML(visible=False)
        gr.Markdown('**Your passage history** · Latest completed attempt per passage/category for the selected skill. '
                    'Repeated attempts and different categories on the same dialogue are not independent evidence of mastery. '
                    'Vocabulary review schedules are unchanged by this activity.')
        history = gr.Dataframe(headers=['Lesson', 'Category', 'Passage', 'Guidance'], datatype=['str'] * 4,
                               interactive=False, label='Completed lesson practice')
        refresh = gr.Button('Refresh lesson history')
    outputs = [identifier, panel, heading, text, audio, *[x for triple in zip(slots, answers, guesses) for x in triple], report]

    def options(cat, sk, mod, les):
        choices = catalog.choices(cat, sk, mod, les)
        counts = ', '.join(f'{CATEGORIES[k].split(" · ")[0]}: {len(catalog.choices(k, sk, mod, les))}' for k in CATEGORIES)
        note = f'Available mapped question pairs — {counts}. '
        note += ('Choose a dialogue. Its lesson reference appears with the study guidance.' if choices else
                 'No mapped passage matches this category and these filters. Try All modules/lessons or another category.')
        return gr.update(choices=[(m['title'], m['id']) for m in choices], value=choices[0]['id'] if choices else None), note, gr.update(interactive=bool(choices))

    for component in (category, skill, module, lesson):
        component.change(safe(options), [category, skill, module, lesson], [passage, coverage, begin], **common)
    for button in auth_buttons:
        button.click(safe(options), [category, skill, module, lesson], [passage, coverage, begin], **common)
        button.click(lambda: [*present({}), []], outputs=[*outputs, history], **common)

    def start(t, mid, sk, cat, mod, les):
        if mid not in {m['id'] for m in catalog.choices(cat, sk, mod, les)}:
            raise ValueError('Choose an available mapped dialogue for these filters')
        return present(store.start_lesson(t, catalog, mid, sk))
    begin.click(safe(start), [token, passage, skill, category, module, lesson], outputs, **common)

    def finish(t, key, a, b, ga, gb, selected_skill):
        state = store.submit_lesson(t, key, [a, b], [ga, gb])
        return [*present(state), history_rows(store, t, selected_skill)]
    submit.click(safe(finish), [token, identifier, *answers, *guesses, skill], [*outputs, history], **common)
    refresh.click(safe(lambda t, sk: history_rows(store, t, sk)), [token, skill], history, **common)
    skill.change(safe(lambda t, sk: history_rows(store, t, sk)), [token, skill], history, **common)
