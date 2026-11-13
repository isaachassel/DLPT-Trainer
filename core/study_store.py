"""Local profile authentication and transactional review history, isolated from assessment."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
import re

from .study_scheduler import day_key, schedule
from .vocabulary_check import VocabularyCheckMixin, check_tables
from .lesson_study import LessonStudyMixin, lesson_tables


class StudyError(ValueError):
    pass


class StudyStore(VocabularyCheckMixin, LessonStudyMixin):
    def __init__(self, path: Path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            check_tables(db)
            lesson_tables(db)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT UNIQUE NOT NULL,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    zone TEXT NOT NULL, new_limit INTEGER NOT NULL DEFAULT 10);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS cards (
                    profile_id TEXT NOT NULL REFERENCES profiles(id), word_id TEXT NOT NULL, skill TEXT NOT NULL,
                    state TEXT NOT NULL, PRIMARY KEY(profile_id, word_id, skill));
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, profile_id TEXT NOT NULL,
                    word_id TEXT NOT NULL, skill TEXT NOT NULL, context_id TEXT,
                    phase TEXT NOT NULL DEFAULT 'question', answer TEXT NOT NULL DEFAULT '',
                    unknown INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL,
                    rating TEXT, result TEXT, prior_reviews INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS reviews (
                    attempt_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, word_id TEXT NOT NULL,
                    skill TEXT NOT NULL, rating TEXT NOT NULL, reviewed REAL NOT NULL,
                    before_state TEXT, after_state TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS reviews_profile ON reviews(profile_id, reviewed);
            ''')
            if 'prior_reviews' not in {r['name'] for r in db.execute('PRAGMA table_info(attempts)')}:
                db.execute('ALTER TABLE attempts ADD COLUMN prior_reviews INTEGER NOT NULL DEFAULT 0')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(str(token).encode()).hexdigest()

    @staticmethod
    def password_hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def create_profile(self, name, password, zone='America/Los_Angeles'):
        name = name.strip()
        if not re.fullmatch(r'[\w .-]{1,40}', name) or not 8 <= len(password) <= 128:
            raise StudyError('Use a profile name of 1–40 letters/numbers and a password of 8–128 characters.')
        day_key(self.clock(), zone)  # Reject unsupported timezone before writing.
        salt = secrets.token_hex(16)
        with self.connect() as db:
            try:
                db.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?,?)',
                           (secrets.token_hex(16), name, name.casefold(), salt,
                            self.password_hash(password, salt), zone, 10))
            except sqlite3.IntegrityError as exc:
                raise StudyError('That profile name already exists. Sign in or choose another name.') from exc
        return self.login(name, password)

    def login(self, name, password):
        if len(password) > 128:
            raise StudyError('Profile name or password is incorrect.')
        with self.connect() as db:
            p = db.execute('SELECT * FROM profiles WHERE name_key=?', (name.strip().casefold(),)).fetchone()
            salt = p['salt'] if p else '00' * 16
            digest = self.password_hash(password, salt)
            if not p or not hmac.compare_digest(digest, p['password_hash']):
                raise StudyError('Profile name or password is incorrect.')
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<?', (self.clock(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',
                       (self.token_hash(token), p['id'], self.clock() + 12 * 3600))
            return token

    def _profile(self, db, token):
        p = db.execute('''SELECT p.id,p.name,p.zone,p.new_limit FROM profiles p JOIN sessions s
                       ON s.profile_id=p.id WHERE s.token_hash=? AND s.expires>?''',
                       (self.token_hash(token), self.clock())).fetchone()
        if not p:
            raise StudyError('Please sign in to your study profile.')
        return dict(p)

    def profile(self, token):
        with self.connect() as db:
            return self._profile(db, token)

    def logout(self, token):
        with self.connect() as db:
            key = self.token_hash(token)
            db.execute('DELETE FROM sessions WHERE token_hash=?', (key,))
            db.execute("UPDATE attempts SET phase='abandoned' WHERE token_hash=? AND phase IN ('question','revealed')", (key,))

    def abandon(self, token):
        with self.connect() as db:
            self._profile(db, token)
            db.execute("UPDATE attempts SET phase='abandoned' WHERE token_hash=? AND phase IN ('question','revealed')",
                       (self.token_hash(token),))

    def set_new_limit(self, token, limit):
        if not isinstance(limit, (float, int)) or int(limit) != limit or not 0 <= limit <= 100:
            raise StudyError('Daily new-word limit must be a whole number from 0 to 100.')
        with self.connect() as db:
            p = self._profile(db, token)
            db.execute('UPDATE profiles SET new_limit=? WHERE id=?', (int(limit), p['id']))

    def states(self, token):
        with self.connect() as db:
            p = self._profile(db, token)
            return {(r['word_id'], r['skill']): json.loads(r['state']) for r in
                    db.execute('SELECT * FROM cards WHERE profile_id=?', (p['id'],))}

    def next_card(self, token, catalog, *, skill='reading', group='Course modules', module='All',
                  lesson='All', context_only=True, exclude=(), focus_only=False):
        eligible = catalog.eligible(skill, group, module, lesson, context_only)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p = self._profile(db, token)
            now = self.clock()
            states = {(r['word_id'], r['skill']): json.loads(r['state']) for r in
                      db.execute('SELECT * FROM cards WHERE profile_id=?', (p['id'],))}
            evidence = self._evidence(db, p['id'], skill)
            def needs_focus(wid):
                card = states.get((wid, skill), {})
                e = evidence.get(wid, {})
                # A successful later review resolves immediate focus; future due reviews still apply.
                return (card.get('last_rating') in ('Again', 'Hard') or card.get('diagnostic_focus') or
                        (e.get('focus', False) and card.get('evidence_reviewed_through', 0) < e.get('last_checked', 0)))
            if focus_only:
                eligible = [wid for wid in eligible if needs_focus(wid)]
            today = day_key(now, p['zone'])
            introduced = sum(s['introduced_day'] == today for s in states.values())
            due = [wid for wid in eligible if wid not in exclude and
                   (wid, skill) in states and states[wid, skill]['due'] <= now]
            due.sort(key=lambda wid: (not needs_focus(wid), states[wid, skill]['due']))
            new = [wid for wid in eligible if wid not in exclude and (wid, skill) not in states]
            new.sort(key=lambda wid: (not needs_focus(wid), wid in evidence,
                                      evidence.get(wid, {}).get('mean', .5)))
            chosen = due[0] if due else (new[0] if new and introduced < p['new_limit'] else None)
            # One active exercise per browser login. Stale submissions cannot alter a new card.
            db.execute("UPDATE attempts SET phase='abandoned' WHERE token_hash=? AND phase IN ('question','revealed')",
                       (self.token_hash(token),))
            if not chosen:
                return None
            previous = states.get((chosen, skill), {})
            context = catalog.context(chosen, skill, previous.get('reviews', 0))
            if skill == 'reading' and needs_focus(chosen):
                fresh = [catalog.contexts[c] for c in catalog.by_word[chosen] if c.startswith('short_')]
                if fresh:
                    context = fresh[0]
            attempt = secrets.token_urlsafe(24)
            db.execute('''INSERT INTO attempts (id,token_hash,profile_id,word_id,skill,context_id,created,prior_reviews)
                       VALUES (?,?,?,?,?,?,?,?)''', (attempt, self.token_hash(token), p['id'], chosen, skill,
                       context['id'] if context else None, now, previous.get('reviews', 0)))
            return attempt

    def _attempt(self, db, token, attempt):
        p = self._profile(db, token)
        a = db.execute('SELECT * FROM attempts WHERE id=? AND token_hash=? AND profile_id=?',
                       (attempt, self.token_hash(token), p['id'])).fetchone()
        if not a or a['phase'] == 'abandoned':
            raise StudyError('This exercise is no longer active. Start another review.')
        return p, dict(a)

    def attempt(self, token, attempt):
        with self.connect() as db:
            return self._attempt(db, token, attempt)[1]

    def reveal(self, token, attempt, answer, unknown=False):
        answer = (answer or '').strip()
        if not unknown and not answer:
            raise StudyError('Type your best guess, or choose “I don’t know”.')
        if len(answer) > 1000:
            raise StudyError('Keep your answer under 1,000 characters.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            _, a = self._attempt(db, token, attempt)
            if a['phase'] != 'question':
                return
            db.execute("UPDATE attempts SET answer=?,unknown=?,phase='revealed' WHERE id=?",
                       (answer, int(unknown), attempt))

    def rate(self, token, attempt, rating):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p, a = self._attempt(db, token, attempt)
            if a['phase'] == 'rated':
                return json.loads(a['result'])  # Retry/double click is idempotent.
            if a['phase'] != 'revealed':
                raise StudyError('Reveal the meaning before rating your recall.')
            if a['unknown'] and rating != 'Again':
                raise StudyError('Use Again when you did not know the answer.')
            old = db.execute('SELECT state FROM cards WHERE profile_id=? AND word_id=? AND skill=?',
                             (p['id'], a['word_id'], a['skill'])).fetchone()
            previous = json.loads(old['state']) if old else None
            # Two browser sessions may display the same word. Reject a stale second update.
            if (previous or {}).get('reviews', 0) != a['prior_reviews']:
                raise StudyError('This word was reviewed in another window. Start another review.')
            now = self.clock()
            if previous is None:
                today = day_key(now, p['zone'])
                introduced = sum(json.loads(r['state'])['introduced_day'] == today for r in
                                 db.execute('SELECT state FROM cards WHERE profile_id=?', (p['id'],)))
                if introduced >= p['new_limit']:
                    raise StudyError('Your daily new-word limit was reached in another window. Start another review.')
            new = schedule(previous, rating, now, p['zone'])
            new['evidence_reviewed_through'] = now
            raw = json.dumps(new)
            db.execute('INSERT OR REPLACE INTO cards VALUES (?,?,?,?)', (p['id'], a['word_id'], a['skill'], raw))
            db.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?)',
                       (attempt, p['id'], a['word_id'], a['skill'], rating, now, old['state'] if old else None, raw))
            db.execute("UPDATE attempts SET phase='rated',rating=?,result=? WHERE id=?", (rating, raw, attempt))
            return new

    def export(self, token):
        with self.connect() as db:
            p = self._profile(db, token)
            cards = [{'word_id': r['word_id'], 'skill': r['skill'], **json.loads(r['state'])}
                     for r in db.execute('SELECT * FROM cards WHERE profile_id=?', (p['id'],))]
            history = [{'word_id': r['word_id'], 'skill': r['skill'], 'rating': r['rating'], 'reviewed': r['reviewed']}
                       for r in db.execute('SELECT * FROM reviews WHERE profile_id=? ORDER BY reviewed', (p['id'],))]
            evidence = [dict(word_id=r['word_id'], skill=r['skill'], **json.loads(r['data'])) for r in
                        db.execute('SELECT * FROM vocabulary_evidence WHERE profile_id=?', (p['id'],))]
            lesson_checks = []
            for row in db.execute('SELECT data FROM lesson_checks WHERE profile_id=?', (p['id'],)):
                state = json.loads(row['data'])
                if state['status'] != 'complete':
                    continue
                mapping = state['mapping']
                lesson_checks.append(dict(skill=state['skill'], completed_at=state['completed_at'],
                    mapping_id=mapping['id'], passage_id=mapping['passage_id'], category=mapping['category'],
                    lesson_id=mapping['lesson_id'], revision=mapping['revision'], results=state['results']))
            return {'version': 3, 'profile': {'name': p['name'], 'timezone': p['zone'], 'new_limit': p['new_limit']},
                    'cards': cards, 'reviews': history, 'vocabulary_checks': evidence, 'lesson_checks': lesson_checks}
