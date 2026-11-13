"""Import the supplied ALES glossary without guessing unit or inherited item IDs."""
import csv
import hashlib
from pathlib import Path

from .vocabulary import ROOT, normalize_ru, term_variants

ALES_PATH = ROOT / 'storage/vocabulary/ales.json'
HEADERS = ['Russian', 'English', 'Basic Course Lesson', 'ALES Item', 'Glossary Page']


def ales_id(russian, english):
    key = normalize_ru(russian) + '\0' + ' '.join(english.casefold().split())
    return 'ales_' + hashlib.sha256(key.encode()).hexdigest()[:24]


def import_ales(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError('ALES CSV exceeds the import size limit')
    items, rows = {}, 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADERS:
            raise ValueError('Expected ALES glossary columns: ' + ', '.join(HEADERS))
        for number, raw in enumerate(reader, 2):
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError(f'Malformed CSV row {number}')
            row = {k: v.strip() for k, v in raw.items()}
            if not any(row.values()):
                continue
            ru, en = row['Russian'], row['English']
            if not ru or not en:
                raise ValueError(f'Missing word or meaning at row {number}')
            for field in ('ALES Item', 'Glossary Page'):
                if row[field] and (not row[field].isascii() or not row[field].isdigit() or int(row[field]) < 1):
                    raise ValueError(f'Invalid {field} at row {number}')
            wid = ales_id(ru, en)
            item = items.setdefault(wid, dict(id=wid, russian=ru, english=en, variants=term_variants(ru),
                                              collection='ales', sources=[]))
            item['sources'].append(dict(group='ALES glossary', lesson='Item ' + row['ALES Item'] if row['ALES Item'] else 'Item not supplied',
                row=number, ales_item=int(row['ALES Item']) if row['ALES Item'] else None,
                glossary_page=int(row['Glossary Page']) if row['Glossary Page'] else None,
                basic_course_lesson=row['Basic Course Lesson'] or None, unit=None))
            rows += 1
    if not items:
        raise ValueError('No ALES vocabulary found')
    return dict(version=1, source_name=path.name, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                report=dict(source_rows=rows, unique_entries=len(items), unit_mapping='not supplied'), items=list(items.values()))
