"""Local Russian vocabulary study. Answers stay on the server until revealed."""
from collections import Counter
from html import escape
import json
import re

import gradio as gr

from core.study_scheduler import mastery, due_label, schedule, RATINGS, day_key
from core.study_store import StudyError
from core.vocabulary import normalize_ru

STUDY_CSS = '''
.study-shell {max-width:1100px;margin:0 auto;padding:18px}
.study-card {padding:24px;border:1px solid #bdcce0;border-radius:12px;line-height:1.85;background:var(--block-background-fill)}
.study-card .russian {font-size:1.3rem;white-space:pre-wrap}
.study-card mark {background:#ffe7a0;color:#16223a;border-radius:3px;padding:0 3px}
.study-card h2 {font-size:1.45rem;margin:0 0 12px}
.study-card .muted {font-size:.9rem;color:var(--body-text-color-subdued)}
.study-answer {border-left:4px solid #2c7799;padding:12px 20px}
'''


def highlighted(text, target):
    parts = re.split('(' + re.escape(target) + ')', text, flags=re.I)
    return ''.join('<mark>' + escape(p) + '</mark>' if i % 2 else escape(p)
                   for i, p in enumerate(parts))


class StudyPresenter:
    """Server-side rendering shared by UI and regression tests."""
    def __init__(self, catalog, store):
        self.catalog, self.store = catalog, store

    def dashboard(self, token, skill, group, module, lesson, context_only):
        profile = self.store.profile(token)
        states = self.store.states(token)
        ids = self.catalog.eligible(skill, group, module, lesson, context_only)
        now = self.store.clock()
        counts = Counter(mastery(states.get((wid, skill))) for wid in ids)
        due = sum((wid, skill) in states and states[wid, skill]['due'] <= now for wid in ids)
        today = day_key(now, profile['zone'])
        introduced = sum(s['introduced_day'] == today for s in states.values())
        progress = ' · '.join(f"{label}: **{counts[label]}**" for label in ['New', 'Learning', 'Shaky', 'Well known'])
        return (f"### {escape(profile['name'])} · {skill.title()}\n\n"
                f"**{due} due now** · {len(ids):,} cards match these filters\n\n{progress}\n\n"
                f"New cards today: {introduced}/{profile['new_limit']} across both skills. "
                f"Review day follows {profile['zone']}. Reading and listening progress are separate.")

    def word_rows(self, token, skill, group, module, lesson, context_only, search='', status='All'):
        states, now = self.store.states(token), self.store.clock()
        result = []
        for wid in self.catalog.eligible(skill, group, module, lesson, context_only):
            word, card = self.catalog.words[wid], states.get((wid, skill))
            label = mastery(card)
            if status != 'All' and label != status:
                continue
            if search and normalize_ru(search) not in normalize_ru(word['russian'] + ' ' + word['english']):
                continue
            result.append([word['russian'], word['english'], label,
                           due_label(card['due'], now) if card else 'Not started',
                           ', '.join(dict.fromkeys(s['group'] + ' / ' + s['lesson'] for s in word['sources']))])
            if len(result) >= 200:
                break
        return result

    def card(self, token, nonce):
        a = self.store.attempt(token, nonce)
        word = self.catalog.words[a['word_id']]
        context = self.catalog.contexts.get(a['context_id'])
        target = context['target'] if context else word['russian']
        heading = f'<h2>What does “{escape(target)}” mean here?</h2>'
        if a['skill'] == 'listening':
            body = '<p>Listen for the target word above. You can replay this study recording as often as you like.</p>'
        elif context:
            body = f'<div class="russian" lang="ru">{highlighted(context["text"], target)}</div>'
        else:
            heading = f'<h2>What does “{escape(target)}” mean?</h2>'
            body = '<p>Word review · A contextual example is not available yet.</p>'
        source = context['source'] if context else 'Imported course vocabulary'
        question = f'<div class="study-card">{heading}{body}<p class="muted">{escape(source)}</p></div>'
        answer = ''
        if a['phase'] in ('revealed', 'rated'):
            meaning = context['meaning'] if context else word['english']
            answer = (f'<div class="study-answer"><h3>{escape(meaning)}</h3>'
                      f'<p>Your guess: {escape(a["answer"]) if not a["unknown"] else "I did not know"}</p>'
                      f'<p>Course entry: <span lang="ru">{escape(word["russian"])}</span> — {escape(word["english"])}</p>')
            if a['skill'] == 'listening' and context:
                answer += f'<div class="russian" lang="ru">{highlighted(context["text"], target)}</div>'
            answer += '<p>Compare the meaning, allowing equivalent English wording. Rate your recall honestly; answers are self-checked.</p></div>'
        return a, question, (context['audio_path'] if context and a['skill'] == 'listening' else None), answer


def build_study_ui(catalog, store):
    presenter = StudyPresenter(catalog, store)
    common = dict(concurrency_id='study-events', concurrency_limit=1, show_progress='minimal', api_visibility='private')
    token = gr.State('')
    session = gr.State({})
    with gr.Column(elem_classes=['study-shell']):
        gr.Markdown('# Russian vocabulary studio\nShort contexts. Honest recall. Reviews when you need them.')
        total = len(catalog.words)
        reading = len(catalog.eligible('reading', 'All vocabulary'))
        listening = len(catalog.eligible('listening', 'All vocabulary'))
        gr.Markdown(f'**{total:,} vocabulary entries** · {reading} with reading contexts · {listening} with listening contexts. '
                    'The context collection is a pilot and does not yet cover the full course.\n\n'
                    'Local study profiles are saved on this computer. This is personal practice, not a DLPT score.')
        if not total:
            gr.Markdown('**Import your course workbook first.** See docs/VOCABULARY_STUDY.md, then restart the app.')
        with gr.Column() as auth:
            with gr.Row():
                name = gr.Textbox(label='Profile name', max_lines=1)
                password = gr.Textbox(label='Password', type='password', max_lines=1)
            zone = gr.Dropdown(['America/Los_Angeles', 'America/Denver', 'America/Chicago', 'America/New_York', 'UTC'],
                               value='America/Los_Angeles', label='Review day timezone (new profiles)')
            with gr.Row():
                login = gr.Button('Sign in', variant='primary')
                create = gr.Button('Create profile')
            gr.Markdown('Use at least 8 password characters. Remember your password: this local preview has no email recovery. '
                        'Passwords are hashed; profiles are not synced online.')
        with gr.Column(visible=False) as workspace:
            with gr.Row():
                skill = gr.Radio([('Reading', 'reading'), ('Listening', 'listening')], value='reading', label='Study skill')
                logout = gr.Button('Sign out', size='sm')
            with gr.Row():
                group = gr.Dropdown(['Course modules', 'Course + ALES + themes', 'All vocabulary'], value='Course modules', label='Vocabulary collection')
                module = gr.Dropdown(['All'] + sorted({s['group'] for w in catalog.words.values() for s in w['sources']}), value='All', label='Module / group')
                lesson = gr.Dropdown(['All'] + sorted({s['lesson'] for w in catalog.words.values() for s in w['sources']}), value='All', label='Lesson')
            context_only = gr.Checkbox(True, label='Only words with context (always required for listening)')
            gr.Markdown('Filters choose your next session. Due cards come first; each session has up to 10 cards. '
                        'Uncheck context-only for word reviews from the rest of the workbook.')
            dashboard = gr.Markdown()
            with gr.Row():
                limit = gr.Number(value=10, minimum=0, maximum=100, precision=0, label='New cards per day (reading + listening)')
                save_limit = gr.Button('Save daily limit')
                start = gr.Button('Start review', variant='primary', interactive=bool(total))
            message = gr.Markdown()
            with gr.Column(visible=False) as exercise:
                question = gr.HTML()
                audio = gr.Audio(type='filepath', visible=False, interactive=False, label='Study recording', buttons=[])
                guess = gr.Textbox(label='Your best guess in English', placeholder='What does the target word mean in this context?', max_lines=3)
                with gr.Row():
                    reveal = gr.Button('Reveal meaning', variant='primary')
                    unknown = gr.Button('I don’t know')
                answer = gr.HTML(visible=False)
                with gr.Row(visible=False) as ratings:
                    rating_buttons = [gr.Button(r) for r in RATINGS]
                gr.Markdown('**Again:** missed it · **Hard:** correct with effort · **Good:** correct · **Easy:** immediate recall')
                with gr.Row():
                    next_button = gr.Button('Next card', interactive=False, variant='primary')
                    skip = gr.Button('Skip without rating')
                    finish = gr.Button('Finish session')
            with gr.Accordion('My vocabulary & progress', open=False):
                with gr.Row():
                    search = gr.Textbox(label='Find a word or meaning')
                    status = gr.Dropdown(['All', 'New', 'Learning', 'Shaky', 'Well known'], value='All', label='Recall')
                    refresh = gr.Button('Refresh list')
                table = gr.Dataframe(headers=['Russian', 'English', 'Recall', 'Next review', 'Source'], datatype=['str'] * 5,
                                     interactive=False, label='Up to 200 matching entries')
                export = gr.Button('Show my progress export')
                exported = gr.Code(language='json', visible=False, label='Copy this JSON to keep a progress record (no password or login tokens)')

    filters = [skill, group, module, lesson, context_only]
    card_outputs = [session, exercise, question, audio, guess, reveal, unknown, answer, ratings, *rating_buttons, next_button, skip, message]

    def safe(fn):
        def wrapped(*args):
            try:
                return fn(*args)
            except (StudyError, ValueError) as exc:
                raise gr.Error(str(exc)) from None
        return wrapped

    def view(t, s, note=''):
        if not s.get('nonce'):
            return [s, gr.update(visible=False), '', gr.update(value=None, visible=False),
                    gr.update(value=''), gr.update(), gr.update(), gr.update(value='', visible=False),
                    gr.update(visible=False), *[gr.update() for _ in RATINGS], gr.update(), gr.update(), note]
        a, q, path, explanation = presenter.card(t, s['nonce'])
        opened, rated = a['phase'] != 'question', a['phase'] == 'rated'
        states = store.states(t)
        old = states.get((a['word_id'], a['skill']))
        labels = [f'{r} · {due_label(schedule(old, r, store.clock(), store.profile(t)["zone"])["due"], store.clock())}' for r in RATINGS]
        return [s, gr.update(visible=True), q, gr.update(value=path, visible=bool(path)),
                gr.update(value=a['answer'], interactive=not opened), gr.update(interactive=not opened),
                gr.update(interactive=not opened), gr.update(value=explanation, visible=opened),
                gr.update(visible=opened and not rated), *[gr.update(value=label, interactive=not rated and (not a['unknown'] or r == 'Again'))
                                          for r, label in zip(RATINGS, labels)],
                gr.update(interactive=rated), gr.update(interactive=not rated),
                f'Card {len(s["seen"]) + 1} of up to 10 · {s["reviewed"]} reviewed. {note}']

    def advance(t, s):
        if len(s['seen']) >= 10:
            return view(t, {**s, 'nonce': None}, f'Session complete. {s["reviewed"]} cards reviewed; progress saved.')
        f = s['filters']
        nonce = store.next_card(t, catalog, skill=f[0], group=f[1], module=f[2], lesson=f[3], context_only=f[4], exclude=s['seen'])
        note = '' if nonce else (f'Session complete: {s["reviewed"]} cards reviewed. No more due or available new cards match '
                                'these filters right now. Your daily limit may have been reached. Try another module, '
                                'enable word reviews for reading, or come back when reviews are due.')
        return view(t, {**s, 'nonce': nonce}, note)

    def authenticate(n, p, z, *f, creating=False):
        t = store.create_profile(n, p, z) if creating else store.login(n, p)
        return [t, '', gr.update(visible=False), gr.update(visible=True), store.profile(t)['new_limit'],
                presenter.dashboard(t, *f), presenter.word_rows(t, *f), gr.update(value='', visible=False), *view(t, {})]

    auth_outputs = [token, password, auth, workspace, limit, dashboard, table, exported, *card_outputs]
    create.click(safe(lambda n, p, z, *f: authenticate(n, p, z, *f, creating=True)), [name, password, zone, *filters], auth_outputs, **common)
    login.click(safe(authenticate), [name, password, zone, *filters], auth_outputs, **common)

    def sign_out(t):
        store.logout(t)
        return ['', gr.update(visible=True), gr.update(visible=False), '', [], gr.update(value='', visible=False), *view('', {})]
    logout.click(safe(sign_out), [token], [token, auth, workspace, dashboard, table, exported, *card_outputs], **common)

    def refresh_data(t, *f):
        return presenter.dashboard(t, *f[:5]), presenter.word_rows(t, *f[:5], *f[5:])
    refresh.click(safe(refresh_data), [token, *filters, search, status], [dashboard, table], **common)
    for component in filters:
        component.change(safe(lambda t, *f: refresh_data(t, *f) if t else (gr.skip(), gr.skip())),
                         [token, *filters, search, status], [dashboard, table], **common)
    def save(t, value, *f):
        store.set_new_limit(t, value)
        return presenter.dashboard(t, *f)
    save_limit.click(safe(save), [token, limit, *filters], [dashboard], **common)
    start.click(safe(lambda t, *f: advance(t, {'nonce': None, 'seen': [], 'reviewed': 0, 'filters': list(f)})),
                [token, *filters], card_outputs, **common)
    def show_answer(t, s, text, didnt_know=False):
        store.reveal(t, s.get('nonce'), text, didnt_know)
        return view(t, s)
    reveal.click(safe(show_answer), [token, session, guess], card_outputs, **common)
    unknown.click(safe(lambda t, s: show_answer(t, s, '', True)), [token, session], card_outputs, **common)
    def rate(t, s, rating, *f):
        result = store.rate(t, s.get('nonce'), rating)
        # Count once even if a browser retries the same rating callback.
        fresh = s.get('counted') != s['nonce']
        s = {**s, 'reviewed': s['reviewed'] + int(fresh), 'counted': s['nonce']}
        return [*view(t, s, f'Saved as {mastery(result).lower()}. Next review {due_label(result["due"], store.clock())}. '
                      'Select Next card to continue.'), presenter.dashboard(t, *f)]
    for button, rating in zip(rating_buttons, RATINGS):
        button.click(safe(lambda t, s, *f, r=rating: rate(t, s, r, *f)), [token, session, *filters], [*card_outputs, dashboard], **common)
    def next_card(t, s, skipping=False):
        a = store.attempt(t, s.get('nonce'))
        if not skipping and a['phase'] != 'rated':
            raise StudyError('Rate your recall first, or skip without rating.')
        return advance(t, {**s, 'seen': [*s['seen'], a['word_id']]})
    next_button.click(safe(next_card), [token, session], card_outputs, **common)
    skip.click(safe(lambda t, s: next_card(t, s, True)), [token, session], card_outputs, **common)
    def finish_session(t, s):
        store.abandon(t)
        return view(t, {**s, 'nonce': None}, f'Session finished. {s.get("reviewed", 0)} cards reviewed; progress saved.')
    finish.click(safe(finish_session), [token, session], card_outputs, **common)
    export.click(safe(lambda t: gr.update(value=json.dumps(store.export(t), ensure_ascii=False, indent=2), visible=True)),
                 [token], [exported], **common)
    return presenter
