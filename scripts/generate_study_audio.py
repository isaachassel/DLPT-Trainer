"""Budgeted, resumable ElevenLabs generation for the original study passages only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.elevenlabs import ElevenLabs
from core.storage import atomic_write_text

VOICES = {'A': 'cgSgspJ2msm6clMCkdW9', 'B': 'cjVigY5qzO86Huf0OWal'}
MODEL = 'eleven_v3'
BUDGET = 8000
SOURCES = ['https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform',
           'https://elevenlabs.io/blog/eleven-v3-is-now-generally-available',
           'https://elevenlabs.io/terms-of-use', 'https://elevenlabs.io/service-specific-terms',
           'https://elevenlabs.io/elevenapi-terms', 'https://elevenlabs.io/speech-engine-terms']
PAID = {'starter', 'creator', 'pro', 'scale', 'business', 'enterprise'}
BATCHES = {'original': ('vocabulary-expansion-20261104', '2026-11-04'),
           'lesson32': ('lesson32-20261108', '2026-11-08'),
           'ales': ('ales-20261113', '2026-11-13')}


def select_batch(passages, batch):
    if batch not in BATCHES:
        raise ValueError('Unknown study audio batch')
    selected = [p for p in passages if p['id'].startswith('ales_')] if batch == 'ales' else [
        p for p in passages if p['id'].startswith('vocab_') and p['id'].startswith('vocab_l32_') == (batch == 'lesson32')]
    if not selected or len({p['id'] for p in selected}) != len(selected):
        raise ValueError('Empty batch or duplicate passage IDs')
    return selected


def publish_records(stage, records, root=ROOT, manifest_relative='data/study/audio.json'):
    """Validate the complete staged batch before publishing; preserve other batches."""
    import shutil
    if manifest_relative not in {'data/study/audio.json', 'data/study/ales/audio.json'}:
        raise ValueError('Unknown audio manifest')
    manifest_path = root / manifest_relative
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else dict(version=1, recordings={})
    for key, record in records.items():
        asset = stage / (key + '.mp3')
        if record['path'] != f'data/study/audio/{key}.mp3' or not key.replace('_', '').isalnum():
            raise ValueError('Invalid recording path')
        if hashlib.sha256(asset.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Staged recording checksum changed')
        decode(asset)
        existing = manifest['recordings'].get(key)
        if existing is not None and existing != record:
            raise ValueError('Refusing to replace an existing recording with different provenance')
    target = root / 'data/study/audio'
    target.mkdir(parents=True, exist_ok=True)
    for key in records:
        shutil.copyfile(stage / (key + '.mp3'), target / (key + '.mp3'))
    manifest['recordings'].update(records)
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2))


def fingerprint(p):
    return hashlib.sha256(json.dumps([p['turns'], MODEL, VOICES], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def decode(path):
    import av
    with av.open(str(path)) as media:
        frames = list(media.decode(audio=0))
    duration = sum(f.samples / f.sample_rate for f in frames)
    if not frames or not 2 <= duration <= 90:
        raise ValueError('Generated recording has an unexpected duration')
    return round(duration, 3)


def main(generate=False, batch='original'):
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    client = ElevenLabs(os.environ.get('ELEVENLABS_API_KEY', ''))
    source = 'data/study/ales/passages.json' if batch == 'ales' else 'data/study/passages.json'
    passages = select_batch(json.loads((ROOT / source).read_text(encoding='utf-8'))['passages'], batch)
    stage = ROOT / 'storage/workshop' / BATCHES[batch][0]
    stage.mkdir(parents=True, exist_ok=True)
    ledger_path = stage / 'ledger.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'attempts': {}, 'budget': BUDGET}
    save = lambda: atomic_write_text(ledger_path, json.dumps(ledger, indent=2))
    catalog = client.catalog()
    account = catalog['account']
    if account['tier'] not in PAID:
        raise ValueError('A current paid plan is required; no generation attempted')
    model = next(m for m in catalog['models'] if m['model_id'] == MODEL)
    rates = model.get('model_rates') or {}
    if not rates or any(rates.get(k, 99) > 1 for k in ('character_cost_multiplier', 'cost_discount_multiplier')):
        raise ValueError('Unexpected model pricing; review before generation')
    available = {v['voice_id']: v for v in catalog['voices']}
    if not all(v in available and available[v]['category'] == 'premade' for v in VOICES.values()):
        raise ValueError('Previously approved premade voices unavailable; no voice substitution')
    total = sum(len(t['text']) for p in passages for t in p['turns'])
    if total > BUDGET or any(sum(len(t['text']) for t in p['turns']) > 2000 for p in passages):
        raise ValueError('Script budget exceeded')
    print(json.dumps({'account': account, 'batch': batch, 'unique_input_characters': total,
                      'maximum_credits_at_checked_rates': total, 'batch_cap': BUDGET}), flush=True)
    if not generate:
        return
    # Prevent simultaneous invocations from spending the same reservations twice.
    lock = ROOT / 'storage/workshop/study-generation.lock'
    with lock.open('x') as handle:
        handle.write('Generation in progress; inspect ledger before removing a stale lock.')
    try:
        ledger.setdefault('account_before', account)
        records = {}
        for p in passages:
            key, digest = p['id'], fingerprint(p)
            prior = ledger['attempts'].get(key)
            if prior:
                if prior['fingerprint'] != digest or prior['status'] != 'succeeded':
                    raise ValueError(f'{key}: previous attempt requires manual review; no automatic retry')
                asset = stage / (key + '.mp3')
                if hashlib.sha256(asset.read_bytes()).hexdigest() != prior['record']['sha256']:
                    raise ValueError('Staged audio checksum changed')
                records[key] = prior['record']
                continue
            amount = sum(len(t['text']) for t in p['turns'])
            reserved = sum(a['input_characters'] for a in ledger['attempts'].values()) + sum(
                a['input_characters'] for a in ledger.get('reviewed_failed_attempts', []))
            if reserved + amount > BUDGET:
                raise ValueError('Reserved budget exhausted')
            live = client._request('GET', '/v1/user/subscription')
            if live['tier'] not in PAID or live['character_limit'] - live['character_count'] < amount:
                raise ValueError('Insufficient existing paid credits; no purchase or overage attempted')
            now = datetime.now(timezone.utc).isoformat()
            ledger['attempts'][key] = dict(status='reserved', fingerprint=digest, input_characters=amount, started_at=now)
            save()  # Reserve before request. Interrupted/uncertain requests never automatically repeat.
            print(key, 'generating', amount, 'characters', flush=True)
            raw = client.dialogue([SimpleNamespace(**t) for t in p['turns']], VOICES, MODEL)
            asset = stage / (key + '.mp3')
            asset.write_bytes(raw)
            duration = decode(asset)
            record = dict(path=f'data/study/audio/{key}.mp3', sha256=hashlib.sha256(raw).hexdigest(),
                          duration_seconds=duration, script_fingerprint=digest, generated_at=now,
                          provider='ElevenLabs', model=MODEL, voice_ids=VOICES, account_tier=live['tier'],
                          input_characters=amount, commercial_use=True, attribution_required=False,
                          model_status='generally_available', terms_checked=BATCHES[batch][1], sources=SOURCES,
                          approval='Standing owner approval of the Jessica/Eric Eleven v3 method; no individual human listening review claimed')
            ledger['attempts'][key].update(status='succeeded', record=record)
            save()
            records[key] = record
        after = client._request('GET', '/v1/user/subscription')
        ledger['account_after'] = {k: after[k] for k in ('tier', 'character_count', 'character_limit')}
        save()
        # Publish only fully decoded, checksum-verified assets after the entire batch succeeds.
        publish_records(stage, records, manifest_relative='data/study/ales/audio.json' if batch == 'ales' else 'data/study/audio.json')
        print('COMPLETE', json.dumps(ledger['account_after']), flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--batch', choices=BATCHES, default='original')
    args = parser.parse_args()
    main(args.generate, args.batch)
