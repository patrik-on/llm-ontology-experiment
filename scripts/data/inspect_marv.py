from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.marv import load_marv


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect MaRV dataset structure.")
    parser.add_argument("--raw-file", default="data/raw/marv/dataset/MaRV.json")
    args = parser.parse_args()

    data = load_marv(args.raw_file)
    print("Refactoring types:")
    total = 0
    for refactoring_type, records in data.items():
        count = len(records) if isinstance(records, list) else 0
        total += count
        print(f"- {refactoring_type}: {count}")
    print(f"Total records: {total}")

    first_type = next(iter(data))
    first_record = data[first_type][0]
    print(f"\nFirst record type: {first_type}")
    print("Available fields:")
    for field in first_record.keys():
        print(f"- {field}")
    print("\nFirst record sample:")
    print(json.dumps(first_record, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
