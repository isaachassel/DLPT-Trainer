"""Passage-based word checks and conservative, context-deduplicated evidence."""
import hashlib
import json
import math
import secrets

UNKNOWN = 'I don’t know'


def evidence_summary(observations):
    """Uniform grid prior; P(correct|knowledge)=1/4+3/4*knowledge.

    One latest observation per word/skill/passage; guessed correct answers have
    quarter weight. No cross-word ability estimate or independence claim.
    """
    latest = {o['source']: o for o in sorted(observations, key=lambda o: o['observed_at'])}
    grid = [i / 100 for i in range(1, 100)]
    logs = []
    for theta in grid:
        score = 0.0
        for o in latest.values():
            p = .25 + .75 * theta
            weight = .25 if o['correct'] and o['guessed'] else 1.0
            score += weight * math.log(p if o['correct'] else 1 - p)
        logs.append(score)
    peak = max(logs)
    weights = [math.exp(x - peak) for x in logs]
    total = sum(weights)
    def quantile(p):
        acc = 0.0
        for x, w in zip(grid, weights):
            acc += w / total
            if acc >= p:
                return x
        return grid[-1]
    last = max(latest.values(), key=lambda o: o['observed_at']) if latest else None
    focus = bool(last and (not last['correct'] or last['guessed']))
    return dict(mean=sum(x * w for x, w in zip(grid, weights)) / total,
                low=quantile(.05), high=quantile(.95), contexts=len(latest),
                focus=focus, last_checked=last['observed_at'] if last else 0,
                label='Needs review' if focus else ('Promising; confirm later' if last else 'Not checked'))


def check_tables(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS vocabulary_checks (
            id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, token_hash TEXT NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vocabulary_evidence (
            profile_id TEXT NOT NULL, word_id TEXT NOT NULL, skill TEXT NOT NULL, source TEXT NOT NULL,
            data TEXT NOT NULL, PRIMARY KEY(profile_id,word_id,skill,source));
    ''')


class VocabularyCheckMixin:
    def _evidence(self, db, profile_id, skill):
        grouped = {}
        for row in db.execute('SELECT * FROM vocabulary_evidence WHERE profile_id=? AND skill=?', (profile_id, skill)):
            grouped.setdefault(row['word_id'], []).append(json.loads(row['data']))
        return {wid: evidence_summary(values) for wid, values in grouped.items()}

    def word_evidence(self, token, skill):
        with self.connect() as db:
            p = self._profile(db, token)
            return self._evidence(db, p['id'], skill)

    def start_check(self, token, catalog, filters, maximum=3):
        if not isinstance(maximum, int) or not 2 <= maximum <= 5:
            raise ValueError('Choose 2–5 passages for a vocabulary check.')
        candidates = catalog.checks(*filters)
        if not candidates:
            raise ValueError('No passage check matches these filters. Try All modules/lessons, or Reading. Individual word reviews are still available.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p = self._profile(db, token)
            identifier = secrets.token_urlsafe(24)
            # Starting a new check cancels an unfinished check from this login.
            for row in db.execute('SELECT id,data FROM vocabulary_checks WHERE token_hash=?', (self.token_hash(token),)).fetchall():
                old = json.loads(row['data'])
                if old['status'] == 'active':
                    old.update(status='cancelled', current=None)
                    db.execute('UPDATE vocabulary_checks SET data=? WHERE id=?', (json.dumps(old), row['id']))
            evidence = self._evidence(db, p['id'], filters[0])
            state = dict(id=identifier, skill=filters[0], filters=list(filters), maximum=maximum,
                         status='active', stage=1, completed=[], current=None, started_at=self.clock(),
                         candidates=candidates, initial_evidence=evidence)
            self._select_check_passage(state)
            db.execute('INSERT INTO vocabulary_checks VALUES (?,?,?,?)',
                       (identifier, p['id'], self.token_hash(token), json.dumps(state)))
            return identifier

    @staticmethod
    def _select_check_passage(state):
        used = {p['id'] for p in state['completed']}
        choices = [p for p in state['candidates'] if p['id'] not in used]
        if len(used) >= state['maximum'] or not choices:
            state.update(status='complete', current=None,
                         end_reason='planned_length' if len(used) >= state['maximum'] else 'content_exhausted')
            return
        evidence = state['initial_evidence']
        def rank(p):
            focus = sum(evidence.get(t['word_id'], {}).get('focus', False) for t in p['targets'])
            unseen = sum(t['word_id'] not in evidence for t in p['targets'])
            tie = hashlib.sha256((state['id'] + p['id']).encode()).hexdigest()
            return abs(p['stage'] - state['stage']), -focus, -unseen, tie
        chosen = min(choices, key=rank)
        questions = []
        for t in chosen['targets']:
            options = [t['meaning'], *t['distractors']]
            secrets.SystemRandom().shuffle(options)
            questions.append({**t, 'options': options})
        state['current'] = {**chosen, 'targets': questions, 'nonce': secrets.token_urlsafe(24)}

    def _check(self, db, token, identifier):
        profile = self._profile(db, token)
        row = db.execute('SELECT data FROM vocabulary_checks WHERE id=? AND profile_id=? AND token_hash=?',
                         (identifier, profile['id'], self.token_hash(token))).fetchone()
        if not row:
            raise ValueError('This vocabulary check is not available in your login.')
        return profile, json.loads(row['data'])

    def check_state(self, token, identifier):
        """Server-only state: never serialize directly into a Gradio component."""
        with self.connect() as db:
            return self._check(db, token, identifier)[1]

    def submit_check(self, token, identifier, nonce, choices, guesses):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            profile, state = self._check(db, token, identifier)
            if state['status'] == 'cancelled':
                raise ValueError('This check was replaced. Start a new check.')
            if any(p['nonce'] == nonce for p in state['completed']):
                return state  # Idempotent retries cannot grade the following passage.
            current = state['current']
            if not current or nonce != current['nonce']:
                raise ValueError('This passage is no longer active.')
            targets = current['targets']
            if len(choices) != len(targets) or len(guesses) != len(targets):
                raise ValueError('Answer every vocabulary question.')
            if any(c not in t['options'] + [UNKNOWN] for t, c in zip(targets, choices)):
                raise ValueError('Answer every question, or choose I don’t know.')
            now = self.clock()
            results = []
            for t, selected, guessed in zip(targets, choices, guesses):
                correct = selected == t['meaning']
                observation = dict(source=current['id'], correct=correct, guessed=bool(guessed),
                                   observed_at=now, check_id=identifier, selected=selected)
                db.execute('INSERT OR REPLACE INTO vocabulary_evidence VALUES (?,?,?,?,?)',
                           (profile['id'], t['word_id'], state['skill'], current['id'], json.dumps(observation)))
                # Misses make an already introduced card due immediately, but never erase its history.
                # A new word remains subject to the ordinary new-card allowance.
                if not correct or guessed:
                    row = db.execute('SELECT state FROM cards WHERE profile_id=? AND word_id=? AND skill=?',
                                     (profile['id'], t['word_id'], state['skill'])).fetchone()
                    if row:
                        card = json.loads(row['state'])
                        card.update(due=min(card['due'], now), diagnostic_focus=True)
                        db.execute('UPDATE cards SET state=? WHERE profile_id=? AND word_id=? AND skill=?',
                                   (json.dumps(card), profile['id'], t['word_id'], state['skill']))
                results.append(dict(word_id=t['word_id'], term=t['term'], target=t['target'], meaning=t['meaning'],
                                    selected=selected, correct=correct, guessed=bool(guessed)))
            state['completed'].append({**current, 'results': results})
            secure = sum(r['correct'] and not r['guessed'] for r in results) / len(results)
            state['stage'] = max(1, min(3, current['stage'] + (1 if secure >= .8 else -1 if secure <= .5 else 0)))
            self._select_check_passage(state)
            db.execute('UPDATE vocabulary_checks SET data=? WHERE id=?', (json.dumps(state), identifier))
            return state

    def cancel_check(self, token, identifier):
        with self.connect() as db:
            p, state = self._check(db, token, identifier)
            if state['status'] == 'active':
                state.update(status='complete', current=None, end_reason='stopped_by_learner')
                db.execute('UPDATE vocabulary_checks SET data=? WHERE id=?', (json.dumps(state), identifier))
            return state
