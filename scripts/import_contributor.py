"""Convert contributor JSON into a new local workshop folder, never the active bank."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.content_intake import IntakePackage, convert_package
from core.preset_bank import ROOT, write_package


def import_file(source: Path, output: Path):
    workshop = (ROOT / 'storage/workshop').resolve()
    output = output.resolve()
    if not output.is_relative_to(workshop) or output == workshop:
        raise ValueError('Output must be a new folder inside storage/workshop')
    package = IntakePackage.model_validate_json(source.read_text(encoding='utf-8-sig'))
    drafts, findings = convert_package(package)
    output.mkdir(parents=True, exist_ok=False)
    write_package(output / 'package.json', drafts)
    (output / 'intake-report.json').write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding='utf-8')
    (output / 'contributor.json').write_text(package.model_dump_json(indent=2), encoding='utf-8')
    return len(drafts.items)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    count = import_file(args.source, args.output)
    print(f'Imported {count} drafts. Read intake-report.json; no content approved or published, no audio generated.')
