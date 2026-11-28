"""Recover static listening drafts from the supplied HTML/Markdown, without executing HTML."""
import argparse
import base64
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.constants import ILR_THETA
from core.models import AudioAsset, GenerationMetadata, PassageItem, QuestionItem
from core.preset_bank import ContentItem, ContentPackage, MANIFEST, Recording, Review, read_package, validate_item, write_package
from core.reading_import import public_url
from core.validation import content_hash, target_unit_count

SKILLS = {
    'contrast': 'relationship of ideas', 'explicit_detail': 'prominent detail',
    'conditional_intention': 'speaker/writer intent', 'main_idea': 'main idea',
    'detail_paraphrase': 'prominent detail', 'explicit_cause': 'cause and effect',
    'alternative_causes': 'cause and effect', 'attributed_explanation': 'cause and effect',
    'idiom_in_context': 'meaning from context', 'motivation': 'speaker/writer intent',
    'qualifying_conclusion': 'relationship of ideas', 'reported_evaluation': 'tone or attitude',
    'sequence': 'sequence', 'speaker_recommendation': 'speaker/writer intent',
    'supported_inference': 'inference',
}
PACK_ID = 'ru-authentic-listening-pilot-01'


def seconds(value):
    minutes, seconds = value.split(':')
    return 60 * int(minutes) + float(seconds)


def decode_duration(data):
    """Fully decode the supplied MP3; do not rewrite or modify it."""
    import imageio_ffmpeg
    with tempfile.TemporaryDirectory(prefix='listening-decode-') as temp:
        path = Path(temp) / 'clip.mp3'
        path.write_bytes(data)
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-xerror',
            '-i', str(path), '-f', 's16le', '-ac', '1', '-ar', '16000', 'pipe:1'],
            capture_output=True, timeout=30)
    if result.returncode or result.stderr or not result.stdout:
        raise ValueError('Audio failed full decoding; restore or review the source recording')
    return len(result.stdout) / 32000


def parse_reviews(html_bytes, markdown_bytes):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_bytes.decode('utf-8-sig'), 'html.parser')
    md = markdown_bytes.decode('utf-8-sig')
    articles = soup.select('article')
    sections = re.findall(r'^### (\d+)\. (.*?)\n(.*?)(?=^### \d+\.|^## Approval rubric)', md, re.M | re.S)
    if len(articles) != 6 or len(sections) != 6:
        raise ValueError('Expected six listening review articles and six matching Markdown sections')
    records, assets, used_ids = [], {}, set()
    for article, (number, heading, body) in zip(articles, sections):
        speaker = article.h2.get_text()
        if not heading.startswith(speaker + ' — '):
            raise ValueError('HTML and Markdown speaker order differs')
        recorded, published_duration, level = re.search(
            r'Recording date: (\d{4}-\d{2}-\d{2}).*?00:00–00:([\d.]+).*?target from transcript: (\S+)', body).groups()
        date.fromisoformat(recorded)
        if f'Transcript target {level}' not in article.get_text():
            raise ValueError('Suggested levels disagree between review files')
        transcripts = article.select('details.transcript p[lang="ru"]')
        captions = []
        for n, p in enumerate(transcripts, 1):
            timing = p.select_one('.time').get_text()
            start, end = timing.split('–')
            text = p.get_text().removeprefix(timing).lstrip()
            if not text or not 0 <= seconds(start) < seconds(end):
                raise ValueError('Invalid caption text or timing')
            captions.append({'id': f'c{n}', 'start': seconds(start), 'end': seconds(end),
                             'timing': timing, 'text': text})
        text = ' '.join(c['text'] for c in captions)
        md_transcript = re.search(r'\*\*Published transcript \(line breaks joined\):\*\*\s+(.*?)\s+\*\*Questions\*\*', body, re.S).group(1)
        if text != md_transcript.strip():
            raise ValueError('Timed captions and published Markdown transcript disagree')
        data_url = article.audio['src']
        if not data_url.startswith('data:audio/mpeg;base64,'):
            raise ValueError('Only embedded MP3 audio is accepted; no remote playback URLs')
        audio = base64.b64decode(data_url.split(',', 1)[1], validate=True)
        duration = decode_duration(audio)
        if abs(duration - float(published_duration)) > .15:
            raise ValueError('Decoded audio duration does not match the review')
        if any(c['start'] >= duration or c['end'] > duration + .15 for c in captions):
            raise ValueError('Caption timing exceeds the allowed source-container discrepancy')
        if any(a['end'] > b['start'] for a, b in zip(captions, captions[1:])):
            raise ValueError('Overlapping or unordered captions require manual review')
        questions = []
        for field in article.select('fieldset'):
            legend = field.legend.get_text()
            qnumber, stem = re.match(r'(\d+\.\d+)\. (.+)', legend).groups()
            inputs = field.select('input[type="radio"]')
            qid = inputs[0]['name']
            if qid in used_ids or any(i['name'] != qid for i in inputs):
                raise ValueError('Question IDs must be unique and consistent')
            used_ids.add(qid)
            options = {i['value']: i.parent.get_text().strip().removeprefix(i['value'] + '.').strip() for i in inputs}
            if len(inputs) != 4 or set(options) != set('ABCD') or len(set(options.values())) != 4:
                raise ValueError('Four distinct A–D choices are required')
            key, skill = re.search(r'\*\*' + re.escape(qnumber) + r': ([A-D]) — ([^*]+)\*\*', body).groups()
            key_line = field.select_one('details p').get_text()
            if not key_line.startswith(f'Answer: {key} · '):
                raise ValueError('Answer keys disagree between HTML and Markdown')
            explanation = key_line.split(' · ', 1)[1]
            if f'**{qnumber}. {stem}**' not in body or any(f'- **{k}.** {v}' not in body for k, v in options.items()):
                raise ValueError('Question wording disagrees between review files')
            block = re.search(r'\*\*' + re.escape(qnumber) + r': .*?\*\*(.*?)(?=\n\*\*\d+\.\d+:|\n\*\*Attribution:)', body, re.S).group(1)
            evidence = []
            for cid, timing, quote in re.findall(r'- (c\d+) · ([^:]+:[\d.]+–[^:]+:[\d.]+): «(.*?)»', block):
                caption = next((c for c in captions if c['id'] == cid), None)
                if not caption or timing != caption['timing'] or quote not in caption['text']:
                    raise ValueError('Evidence must exactly match its referenced caption and timestamp')
                evidence.append({'caption_id': cid, 'timing': timing, 'quote_ru': quote})
            if not evidence:
                raise ValueError('Every question needs timed caption evidence')
            if field.select_one('p.note').get_text() != 'Evidence: ' + ', '.join(e['timing'] for e in evidence):
                raise ValueError('HTML and Markdown evidence references disagree')
            rationales = dict(re.findall(r'- \*\*([A-D]):\*\* (.+)', block))
            if set(rationales) != set('ABCD') or explanation not in block:
                raise ValueError('Missing explanation or option rationales')
            questions.append({'id': qid, 'stem_en': stem, 'skill': skill, 'choices': options,
                'correct_key': key, 'explanation_en': explanation, 'evidence': evidence,
                'option_rationales': rationales})
        pid = questions[0]['id'].rsplit('-q', 1)[0]
        if not re.fullmatch(r'ru-listen-pilot01-[a-z]+', pid) or pid in used_ids or any(not q['id'].startswith(pid + '-q') for q in questions):
            raise ValueError('Invalid or duplicate passage ID')
        used_ids.add(pid)
        links = {a.get_text(): a['href'] for a in article.select('details a')}
        for name in ('Audio source', 'Caption revision', 'Audio license', 'Caption license'):
            if not public_url(links.get(name, '')):
                raise ValueError('Missing source or license URL')
        if links['Audio license'] != 'https://creativecommons.org/licenses/by/3.0/' or links['Caption license'] != 'https://creativecommons.org/licenses/by-sa/4.0/':
            raise ValueError('Unexpected licensing; manual adapter review required')
        original_audio = re.search(r'\[Direct original audio\]\(([^)]+)\)', body).group(1)
        attribution = re.search(r'\*\*Attribution:\*\* (.+)', body).group(1)
        if any(url not in body for url in links.values()) or not public_url(original_audio):
            raise ValueError('Source references disagree')
        review_details = article.select_one('details.transcript').find_all('p', recursive=False)
        records.append({'id': pid, 'family_id': pid, 'speaker': speaker,
            'topic': heading.split(' — ', 1)[1], 'recording_date': recorded, 'provisional_ilr': level,
            'review_status': 'draft', 'diagnostic_eligible': False, 'calibrated': False,
            'transcript': text, 'captions': captions, 'questions': questions,
            'duration_seconds': duration, 'reported_ogg_duration_seconds': float(published_duration),
            'caption_overrun_seconds': round(max(0, captions[-1]['end'] - duration), 5),
            'difficulty_rationale': review_details[0].get_text(),
            'auditory_review_focus': review_details[1].get_text().removeprefix('Review focus: '),
            'source': links, 'original_audio_url': original_audio, 'attribution': attribution,
            'audio_sha256': sha256(audio).hexdigest(),
            'audio_note': 'MP3 recovered byte-for-byte from the supplied HTML. No re-encoding, speed change, denoising or generated speech.'})
        assets[pid] = audio
    if sum(len(r['questions']) for r in records) != 17:
        raise ValueError('Expected 17 questions across this pilot')
    return records, assets


def convert_records(records, version=1):
    items = []
    metadata = GenerationMetadata(provider='contributor import', model='unspecified question authoring',
        prompt_version=PACK_ID, generated_at='2026-11-27T00:00:00Z',
        authoring_notes='Authentic radio excerpts and published captions. Newly authored questions; auditory/teacher review pending.')
    for r in records:
        level, pid = r['provisional_ilr'], r['id']
        questions = [QuestionItem(id=q['id'], passage_id=pid, stem_en=q['stem_en'], choices=q['choices'],
            correct_key=q['correct_key'], rationale_en=q['explanation_en'], evidence_ru=q['evidence'][0]['quote_ru'],
            question_type=SKILLS[q['skill']], target_ilr=level, provisional_difficulty=ILR_THETA[level],
            generation=metadata, created_at=metadata.generated_at,
            answer_position_metadata={'source_skill': q['skill'], 'stable_option_ids': {k:k for k in 'ABCD'}})
            for q in r['questions']]
        digest = content_hash(r['transcript'])
        passage = PassageItem(id=pid, family_id=pid, skill='listening', target_ilr=level,
            provisional_difficulty=ILR_THETA[level], genre='radio excerpt', topic=r['topic'], subtopic='Published radio speech',
            orientation_en='Listen to a short excerpt from a radio broadcast.', passage_ru=r['transcript'],
            source_type='authentic/open-licensed', license='CC BY-SA 4.0 (published captions)',
            provenance={'source_title': r['speaker'] + ' — radio excerpt', 'source_author': r['speaker'],
                'source_publisher': 'Echo of Moscow radio station archive', 'publication_date': r['recording_date'],
                'source_original_url': r['source']['Audio source'], 'source_license_url': r['source']['Audio license'],
                'audio_license': 'CC BY 3.0', 'audio_license_url': r['source']['Audio license'],
                'caption_license': 'CC BY-SA 4.0', 'caption_license_url': r['source']['Caption license'],
                'caption_source_url': r['source']['Caption revision'], 'caption_author': 'Wikimedia Commons contributors',
                'source_archive_publisher': 'Wikimedia Commons', 'source_archive_revision_url': r['source']['Audio source'],
                'source_license_basis': 'Per-file Commons license notice and Echo of Moscow media project release. Applies to this released excerpt, not the full program.',
                'source_license_evidence_url': r['source']['Audio source'], 'original_audio_url': r['original_audio_url'],
                'selection': 'Full released excerpt retained; MP3 is a format conversion.',
                'modifications': r['audio_note'] + ' Published timed caption lines joined into prose; source repetitions retained.',
                'difficulty_rationale': r['difficulty_rationale'], 'auditory_review_focus': r['auditory_review_focus'],
                'attribution': r['attribution'], 'pack_id': PACK_ID}, word_count=target_unit_count(r['transcript'], 'ru'),
            audio_duration_seconds=r['duration_seconds'], question_ids=[q.id for q in questions], audio_asset_id=pid+'-audio',
            content_hash=digest, duplicate_detection_hash=digest, generation=metadata, created_at=metadata.generated_at)
        audio = AudioAsset(id=passage.audio_asset_id, source_type='authentic/open-licensed', path=f'audio/{r["audio_sha256"]}.mp3',
            content_hash=r['audio_sha256'], transcript_hash=digest, duration_seconds=r['duration_seconds'],
            license='CC BY 3.0', synthetic_tts=False, validated=False, engine='Source MP3 format conversion')
        items.append(ContentItem(id=pid, content_version=version, passage=passage, questions=questions,
            audio=audio, audio_sha256=r['audio_sha256'], authoring_record=r,
            recording=Recording(provider='authentic radio', model='not applicable',
                usage_terms='Audio CC BY 3.0; published captions CC BY-SA 4.0. Attribution required. No synthesized voices.'),
            review=Review(notes='Pending normal-speed audition, caption accuracy, source rights, question and level review.')))
    return ContentPackage(items=items)


def import_files(html_path, markdown_path, output, version=1):
    if output.resolve() == MANIFEST.resolve():
        raise ValueError('Import drafts, never the active assessment manifest')
    html_bytes, md_bytes = html_path.read_bytes(), markdown_path.read_bytes()
    records, assets = parse_reviews(html_bytes, md_bytes)
    package = convert_records(records, version)
    archive = output.parent / 'versions' / f'v{version}'
    for name, data in [('listening_review.html', html_bytes), ('listening_review.md', md_bytes)]:
        if (archive / name).exists() and (archive / name).read_bytes() != data:
            raise ValueError('Source changed: increase --version; original submissions are immutable')
    if output.exists():
        prior = read_package(output)
        if prior != package and version <= max(i.content_version for i in prior.items):
            raise ValueError('Increase --version to revise a draft; preserve previous records')
    # Validate everything in a temporary package before making the import visible.
    with tempfile.TemporaryDirectory(prefix='listening-package-') as temp:
        base = Path(temp)
        (base / 'audio').mkdir()
        for item in package.items:
            (base / item.audio.path).write_bytes(assets[item.id])
            validate_item(item, base)
    if output.exists() and read_package(output) == package:
        for item in package.items:
            validate_item(item, output.parent)
        return package
    archive.mkdir(parents=True, exist_ok=True)
    (archive / 'listening_review.html').write_bytes(html_bytes)
    (archive / 'listening_review.md').write_bytes(md_bytes)
    (output.parent / 'audio').mkdir(exist_ok=True)
    for item in package.items:
        (output.parent / item.audio.path).write_bytes(assets[item.id])
    write_package(archive / 'package.json', package)
    write_package(output, package)
    return package


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html', type=Path, required=True)
    p.add_argument('--markdown', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--version', type=int, default=1)
    args = p.parse_args()
    pack = import_files(args.html, args.markdown, args.output, args.version)
    print(f'Imported {len(pack.items)} drafts / {sum(len(i.questions) for i in pack.items)} questions. No generation, approval or publication.')
