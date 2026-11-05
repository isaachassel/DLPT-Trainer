"""Study-only contexts linked by explicit Russian form AND English sense hints."""
import hashlib
import json
from pathlib import Path
import re

from .vocabulary import ROOT, load_vocabulary, normalize_ru


class StudyCatalog:
    def __init__(self, vocabulary_path=None, contexts_path=None, bank_path=None, passages_path=None):
        raw = load_vocabulary(vocabulary_path) if vocabulary_path else load_vocabulary()
        self.words = {w['id']: w for w in raw['items']}
        self.report = raw.get('report', {})
        self.contexts = {}
        self.by_word = {wid: [] for wid in self.words}
        self.unlinked_contexts = []
        self.passages = {}
        seeds = json.loads((contexts_path or ROOT / 'data/study/contexts.json').read_text(encoding='utf-8'))
        if passages_path or contexts_path is None:
            source = passages_path or ROOT / 'data/study/passages.json'
            if source.exists():
                self._load_passages(source, seeds)
        bank_file = bank_path or ROOT / 'data/assessment/bank.json'
        bank = {i['id']: i for i in json.loads(bank_file.read_text(encoding='utf-8'))['items']}
        for seed in seeds:
            context = dict(seed)
            context.setdefault('audio_path', None)
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
            elif not context.get('source'):
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
        for passage in self.passages.values():
            for target in passage['targets']:
                target['word_ids'] = [wid for wid, ids in self.by_word.items() if 'short_' + target['id'] in ids]

    def _load_passages(self, source, seeds):
        audio_file = source.parent / 'audio.json'
        recordings = json.loads(audio_file.read_text(encoding='utf-8'))['recordings'] if audio_file.exists() else {}
        raw = json.loads(source.read_text(encoding='utf-8'))
        seen = set()
        for passage in raw['passages']:
            pid = passage['id']
            if pid in seen or passage['language'] != 'ru' or passage['stage'] not in (1, 2, 3):
                raise ValueError('Invalid vocabulary passage identifier, language or stage')
            seen.add(pid)
            passage['text'] = '\n\n'.join(t['speaker'] + ': ' + t['text'] for t in passage['turns'])
            passage['audio_path'] = None
            record = recordings.get(pid)
            if record:
                fingerprint = hashlib.sha256(json.dumps([passage['turns'], record['model'], record['voice_ids']],
                                                        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                path = (ROOT / record['path']).resolve()
                if (record['account_tier'] not in {'starter', 'creator', 'pro', 'scale', 'business', 'enterprise'}
                    or record.get('commercial_use') is not True or record.get('attribution_required') is not False
                    or record.get('model_status') != 'generally_available' or record['script_fingerprint'] != fingerprint
                    or not path.is_relative_to((ROOT / 'data/study/audio').resolve()) or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']):
                    raise ValueError(f'Invalid study audio provenance: {pid}')
                passage['audio_path'] = str(path)
            target_ids = set()
            for t in passage['targets']:
                if t['id'] in target_ids or len(t['distractors']) != 3 or len(set([t['meaning'], *t['distractors']])) != 4:
                    raise ValueError('Each vocabulary question needs four distinct meanings and a unique ID')
                target_ids.add(t['id'])
                base = {k: t[k] for k in ('term', 'sense_hints', 'target', 'meaning')}
                seeds.append(dict(base, id='short_' + t['id'], target=t['review_target'],
                                  text=t['review_text'], source='New study example; provisional language review'))
                seeds.append(dict(base, id='long_' + t['id'], text=passage['text'], audio_path=passage['audio_path'],
                                  source='Original study dialogue; synthetic audio; provisional language review'))
            self.passages[pid] = passage

    def checks(self, skill='reading', group='Course modules', module='All', lesson='All', context_only=True):
        eligible = set(self.eligible(skill, group, module, lesson, context_only))
        result = []
        for passage in self.passages.values():
            if skill == 'listening' and not passage['audio_path']:
                continue
            targets = []
            for t in passage['targets']:
                matches = [wid for wid in t['word_ids'] if wid in eligible]
                if matches:
                    # Test a sense once, not duplicate workbook rows/variants as independent questions.
                    targets.append({**t, 'word_id': matches[0]})
            if len(targets) >= 2:
                result.append({**passage, 'targets': targets[:6]})
        return result

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
