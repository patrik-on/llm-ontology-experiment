from __future__ import annotations

import argparse
import sys
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.methods2test import (
    ALLOWED_CONTEXT_FIELDS,
    collect_subset,
    corpus_files,
    read_corpus_file,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Methods2Test corpus/json files.")
    parser.add_argument("--raw-dir", default="data/raw/methods2test/corpus/json")
    parser.add_argument("--context-field", default="src_fm", choices=ALLOWED_CONTEXT_FIELDS)
    parser.add_argument("--examples", type=int, default=3)
    parser.add_argument("--stats-sample", type=int, default=1000)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    print("Detected corpus files:")
    for split in ("train", "eval", "test"):
        files = corpus_files(raw_dir, split)
        print(f"- {split}: {len(files)} files")

    for split in ("train", "eval", "test"):
        print(f"\nExamples from {split}:")
        for path in islice(corpus_files(raw_dir, split), args.examples):
            payload = read_corpus_file(path)
            input_text = str(payload.get(args.context_field, "")).strip()
            output_text = str(payload.get("target", "")).strip()
            print(f"- {path}")
            print(f"  input_chars={len(input_text)}, output_chars={len(output_text)}")
            print(f"  input: {input_text[:500]}")
            print(f"  output: {output_text[:500]}")

        loaded, skipped, records = collect_subset(raw_dir, split, args.context_field, args.stats_sample)
        avg_input = sum(len(record["input"]) for record in records) / len(records) if records else 0.0
        avg_output = sum(len(record["output"]) for record in records) / len(records) if records else 0.0
        print(f"Loaded files for stats: {loaded}")
        print(f"Skipped examples for stats: {skipped}")
        print(f"Filtered sample size: {len(records)}")
        print(f"Average input length: {avg_input:.2f}")
        print(f"Average output length: {avg_output:.2f}")


if __name__ == "__main__":
    main()
