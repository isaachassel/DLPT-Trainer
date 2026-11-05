"""Read-only course vocabulary import. No macros, formulas or external links run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from .storage import atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_PATH = ROOT / 'storage/vocabulary/course.json'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def normalize_ru(value: str) -> str:
    unstressed = unicodedata.normalize('NFC', ''.join(c for c in unicodedata.normalize('NFD', value)
                                                   if c != '\u0301'))
    return ' '.join(unstressed.lower().replace('ё', 'е').split())


def term_variants(value: str) -> list[str]:
    text = re.sub(r'\([^)]*\)', '', value)
    terms = []
    for part in re.split(r'[/;,]', text):
        part = re.split(r'\+|\[', part)[0].strip().strip('!? .')
        if part.startswith('-') or not re.fullmatch(r'[А-Яа-яЁё\u0301 -]+', part):
            continue
        term = normalize_ru(part)
        if term and term not in terms:
            terms.append(term)
    return terms


def import_workbook(path: Path) -> dict:
    """Use the compiled sheet once; keep module/lesson provenance for duplicates."""
    with ZipFile(path) as archive:
        # Bound expanded XML; images are neither read nor copied.
        if any(i.file_size > 50_000_000 for i in archive.infolist() if i.filename.endswith('.xml')):
            raise ValueError('Workbook XML exceeds the import size limit')
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheet = next((s for s in workbook.findall('s:sheets/s:sheet', NS)
                      if normalize_ru(s.get('name', '')) == 'все слова'), None)
        if sheet is None:
            raise ValueError('Expected the combined vocabulary sheet "всё слова"; no other sheets were guessed')
        rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        link = next((r for r in relationships if r.get('Id') == rid), None)
        if link is None or link.get('TargetMode') == 'External':
            raise ValueError('Vocabulary worksheet must be inside the workbook')
        target = link.get('Target', '')
        name = target.lstrip('/') if target.startswith('/xl/') else 'xl/' + target
        if '..' in PurePosixPath(name).parts or not name.startswith('xl/worksheets/'):
            raise ValueError('Unsafe worksheet relationship')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//s:t', NS))
                       for si in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        grouped, skipped, counts = {}, [], Counter()
        rows = ET.fromstring(archive.read(name)).findall('s:sheetData/s:row', NS)
        for row in rows:
            values, formula = {}, False
            for cell in row.findall('s:c', NS):
                col = re.sub(r'\d', '', cell.get('r', ''))
                if col not in ('A', 'B', 'C', 'D'):
                    continue
                if cell.find('s:f', NS) is not None:
                    formula = True
                value = cell.find('s:v', NS)
                raw = value.text if value is not None else ''
                if cell.get('t') == 's' and raw:
                    raw = strings[int(raw)]
                elif cell.get('t') == 'inlineStr':
                    raw = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
                values[col] = (raw or '').strip()
            if not any(values.values()):
                continue
            if formula or not values.get('C') or not values.get('D') or not re.search('[А-Яа-яЁё]', values['C']):
                skipped.append({'row': row.get('r'), 'reason': 'formula or incomplete/non-Russian vocabulary'})
                continue
            group, lesson, word, meaning = (values.get(c, '') for c in 'ABCD')
            key = normalize_ru(word) + '\0' + ' '.join(meaning.casefold().split())
            word_id = 'v_' + hashlib.sha256(key.encode()).hexdigest()[:24]
            item = grouped.setdefault(word_id, {'id': word_id, 'russian': word, 'english': meaning,
                'variants': term_variants(word), 'sources': []})
            item['sources'].append({'sheet': sheet.get('name'), 'row': int(row.get('r')),
                                    'group': group, 'lesson': lesson})
            counts[group] += 1
        if not grouped:
            raise ValueError('No vocabulary entries found')
    return {'version': 1, 'source_name': path.name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'report': {'source_rows': sum(counts.values()), 'unique_entries': len(grouped),
                       'rows_by_group': dict(counts), 'skipped': skipped}, 'items': list(grouped.values())}


def save_vocabulary(data: dict, path: Path = VOCABULARY_PATH) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_vocabulary(path: Path = VOCABULARY_PATH) -> dict:
    if not path.exists():
        return {'version': 1, 'items': [], 'report': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('Unsupported vocabulary catalog')
    ids = [i['id'] for i in data['items']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate vocabulary IDs')
    return data
