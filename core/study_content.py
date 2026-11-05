"""Study-only contexts linked by explicit Russian form AND English sense hints."""
import hashlib
import json
from pathlib import Path
import re

from .vocabulary import ROOT, load_vocabulary, normalize_ru


class StudyCatalog:
    def __init__(self, vocabulary_path=None, contexts_path=None, bank_path=None):
        raw = load_vocabulary(vocabulary_path) if vocabulary_path else load_vocabulary()
        self.words = {w['id']: w for w in raw['items']}
        self.report = raw.get('report', {})
        self.contexts = {}
        self.by_word = {wid: [] for wid in self.words}
        self.unlinked_contexts = []
        seeds = json.loads((contexts_path or ROOT / 'data/study/contexts.json').read_text(encoding='utf-8'))
        bank_file = bank_path or ROOT / 'data/assessment/bank.json'
        bank = {i['id']: i for i in json.loads(bank_file.read_text(encoding='utf-8'))['items']}
        for seed in seeds:
            context = dict(seed)
            context['audio_path'] = None
            if seed.get('passage_id'):
                item = bank.get(seed['passage_id'])
                if not item or item['review']['status'] != 'approved':
                    continue
                context['text'] = item['passage']['passage_ru']
                # Reuse the approved full short recording. Never splice untimed audio.
                audio = item.get('audio')
                if audio and (audio.get('duration_seconds') or 999) <= 65:
                    path = (ROOT / audio['path']).resolve()
                    if (path.is_relative_to((ROOT / 'data/assessment/audio').resolve()) and path.is_file()
                            and hashlib.sha256(path.read_bytes()).hexdigest() == item['audio_sha256']):
                        context['audio_path'] = str(path)
                context['source'] = 'Approved project dialogue; synthetic audio'
            else:
                context['source'] = 'Original study example; provisional language review'
            if not re.search(r'(?<!\w)' + re.escape(seed['target']) + r'(?!\w)', context['text'], re.I):
                raise ValueError(f"Context target missing: {seed['id']}")
            self.contexts[seed['id']] = context
            linked = False
            for word in self.words.values():
                if (normalize_ru(seed['term']) in word['variants'] and
                        any(h.casefold() in word['english'].casefold() for h in seed['sense_hints'])):
                    self.by_word[word['id']].append(seed['id'])
                    linked = True
            if not linked:
                self.unlinked_contexts.append(seed['id'])

    def eligible(self, skill='reading', group='Course modules', module='All', lesson='All', context_only=True):
        if skill not in ('reading', 'listening'):
            raise ValueError('Choose reading or listening')
        result, ranks = [], {}
        def natural(text):
            return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                         for part in re.split(r'(\d+)', text))
        for word in self.words.values():
            sources = word['sources']
            sources = [s for s in sources if (group == 'All vocabulary' or
                       (group == 'Course modules' and s['group'].startswith('Mod ')) or
                       (group == 'Course + ALES + themes' and s['group'] != 'Frequency'))]
            if module != 'All':
                sources = [s for s in sources if s['group'] == module]
            if lesson != 'All':
                sources = [s for s in sources if s['lesson'] == lesson]
            if not sources:
                continue
            contexts = [self.contexts[c] for c in self.by_word[word['id']]]
            if skill == 'listening':
                contexts = [c for c in contexts if c['audio_path']]
            if not contexts and (context_only or skill == 'listening'):
                continue
            result.append(word['id'])
            ranks[word['id']] = min((0 if s['group'].startswith('Mod ') else 1,
                                     natural(s['group']), natural(s['lesson']), s['row']) for s in sources)
        return sorted(result, key=lambda wid: (ranks[wid], wid))

    def context(self, word_id, skill, review_count=0):
        choices = [self.contexts[c] for c in self.by_word[word_id]
                   if skill == 'reading' or self.contexts[c]['audio_path']]
        return choices[review_count % len(choices)] if choices else None
