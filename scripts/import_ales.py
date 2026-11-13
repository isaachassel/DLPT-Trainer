"""Import ALES CSV into ignored local storage; original CSV remains unchanged."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.ales import ALES_PATH, import_ales
from core.vocabulary import save_vocabulary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--output', type=Path, default=ALES_PATH)
    args = parser.parse_args()
    data = import_ales(args.csv)
    save_vocabulary(data, args.output)
    print(f"Imported {data['report']['source_rows']} rows / {len(data['items'])} entries. Unit mapping not supplied.")
