"""Explicit, provisional passage-to-competency mappings and local practice evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets

CATEGORIES = {
    'lexical': 'Lexical · Vocabulary',
    'structural': 'Structural · Grammar',
    'discourse': 'Discourse · Meaning across the passage',
    'sociocultural': 'Sociocultural · Register and social context',
}
UNKNOWN = 'I don’t know'
ROOT = Path(__file__).resolve().parents[1]


class LessonCatalog:
    def __init__(self, study, path=None):
        raw = json.loads((path or ROOT / 'data/study/lesson_mappings.json').read_text(encoding='utf-8'))
        if raw.get('version') != 1:
            raise ValueError('Unsupported lesson mapping version')
        self.lessons = {x['id']: x for x in raw['lessons']}
        if len(self.lessons) != len(raw['lessons']):
            raise ValueError('Duplicate lesson ID')
        self.mappings = {}
        question_ids = set()
        for source in raw['mappings']:
            item = deepcopy(source)
            pid, key = item['passage_id'], item['id']
            if key in self.mappings or pid not in study.passages or item['category'] not in CATEGORIES:
                raise ValueError('Invalid or duplicate passage/category mapping')
            if item['lesson_id'] is not None and item['lesson_id'] not in self.lessons:
                raise ValueError('Unknown lesson reference')
            passage = study.passages[pid]
            lesson = self.lessons.get(item['lesson_id'])
            if lesson and lesson['language'] != passage['language']:
                raise ValueError('Lesson language does not match passage')
            if len(item['questions']) != 2 or not item['objective'].strip() or not item['review_guidance'].strip():
                raise ValueError('A lesson mapping needs two questions and review guidance')
            for q in item['questions']:
                options = [q['answer'], *q['distractors']]
                if (q['id'] in question_ids or len(options) != 4 or len(set(options)) != 4
                        or UNKNOWN in options or any(not isinstance(x, str) or not x.strip() for x in options)
                        or not q['prompt'].strip() or not q['explanation'].strip()
                        or not q['evidence'].strip() or q['evidence'].casefold() not in passage['text'].casefold()):
                    raise ValueError('Invalid lesson question, choices or passage evidence')
                question_ids.add(q['id'])
            item['revision'] = hashlib.sha256(json.dumps([source, passage['text']], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            item.update(title=passage['title'], text=passage['text'], audio_path=passage['audio_path'],
                        language=passage['language'], lesson=deepcopy(lesson))
            self.mappings[key] = item

    def choices(self, category='lexical', skill='reading', module='All', lesson='All'):
        if category not in CATEGORIES or skill not in ('reading', 'listening'):
            raise ValueError('Choose a supported category and skill')
        return [m for m in self.mappings.values() if m['category'] == category
                and (skill == 'reading' or m['audio_path'])
                and (module == 'All' or m['lesson'] and m['lesson']['module'] == module)
                and (lesson == 'All' or m['lesson'] and m['lesson']['lesson'] == lesson)]


def recommendation(results):
    if len(results) != 2:
        return 'Not checked yet'
    correct = sum(r['correct'] for r in results)
    if correct == 0:
        return 'Prioritize this lesson'
    if correct == 1:
        return 'Review this lesson'
    if any(r['guessed'] for r in results):
        return 'Review to build confidence'
    return 'Looking good so far'


def lesson_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS lesson_checks (
        id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, token_hash TEXT NOT NULL, data TEXT NOT NULL)''')


class LessonStudyMixin:
    def start_lesson(self, token, catalog, mapping_id, skill):
        if skill not in ('reading', 'listening') or mapping_id not in catalog.mappings:
            raise ValueError('Choose an available passage and skill')
        mapping = deepcopy(catalog.mappings[mapping_id])
        if skill == 'listening' and not mapping['audio_path']:
            raise ValueError('This passage has no verified recording')
        for q in mapping['questions']:
            q['options'] = [q['answer'], *q['distractors']]
            secrets.SystemRandom().shuffle(q['options'])
        state = dict(id=secrets.token_urlsafe(24), skill=skill, mapping=mapping,
                     status='active', results=[], started_at=self.clock())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p = self._profile(db, token)
            # A new lesson passage replaces unfinished lesson work for this login.
            for row in db.execute('SELECT id,data FROM lesson_checks WHERE token_hash=?', (self.token_hash(token),)).fetchall():
                old = json.loads(row['data'])
                if old['status'] == 'active':
                    old['status'] = 'cancelled'
                    db.execute('UPDATE lesson_checks SET data=? WHERE id=?', (json.dumps(old), row['id']))
            db.execute('INSERT INTO lesson_checks VALUES (?,?,?,?)',
                       (state['id'], p['id'], self.token_hash(token), json.dumps(state)))
        return state

    def _lesson_state(self, db, token, identifier):
        p = self._profile(db, token)
        row = db.execute('SELECT data FROM lesson_checks WHERE id=? AND profile_id=? AND token_hash=?',
                         (identifier, p['id'], self.token_hash(token))).fetchone()
        if not row:
            raise ValueError('This lesson check is not available in your login')
        return json.loads(row['data'])

    def submit_lesson(self, token, identifier, answers, guesses):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._lesson_state(db, token, identifier)
            if state['status'] == 'complete':
                return state
            if state['status'] != 'active':
                raise ValueError('This lesson check was replaced; start another passage')
            questions = state['mapping']['questions']
            if (len(answers) != 2 or len(guesses) != 2 or any(type(g) is not bool for g in guesses)
                    or any(a not in q['options'] + [UNKNOWN] for a, q in zip(answers, questions))):
                raise ValueError('Answer both questions, or choose I don’t know')
            state['results'] = [dict(question_id=q['id'], selected=a, correct=a == q['answer'], guessed=g)
                                for q, a, g in zip(questions, answers, guesses)]
            state.update(status='complete', completed_at=self.clock())
            db.execute('UPDATE lesson_checks SET data=? WHERE id=?', (json.dumps(state), identifier))
            return state

    def lesson_history(self, token, skill=None):
        with self.connect() as db:
            p = self._profile(db, token)
            data = [json.loads(r['data']) for r in db.execute('SELECT data FROM lesson_checks WHERE profile_id=?', (p['id'],))]
        # Preserve attempts in storage; display latest per passage/category/skill.
        # Edited questions and repeats do not manufacture independent passages.
        latest = {}
        for s in sorted(data, key=lambda s: s.get('completed_at', 0)):
            if s['status'] == 'complete' and (skill is None or s['skill'] == skill):
                m = s['mapping']
                latest[m['passage_id'], m['category'], s['skill']] = s
        return list(latest.values())
