"""Import the combined course vocabulary sheet into ignored local storage."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.vocabulary import import_workbook, save_vocabulary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    args = parser.parse_args()
    data = import_workbook(args.workbook)
    save_vocabulary(data)
    print(data['report'])
