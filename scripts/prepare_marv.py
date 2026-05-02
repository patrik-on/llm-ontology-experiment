from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.marv import prepare_marv


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare MaRV refactoring instruction-tuning dataset.")
    parser.add_argument("--raw-file", default="data/raw/marv/dataset/MaRV.json")
    parser.add_argument("--out-dir", default="data/processed/refactoring")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-input-chars", type=int, default=12000)
    parser.add_argument("--max-output-chars", type=int, default=12000)
    args = parser.parse_args()

    stats = prepare_marv(
        raw_file=args.raw_file,
        out_dir=args.out_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        max_input_chars=args.max_input_chars,
        max_output_chars=args.max_output_chars,
    )

    print("MaRV preparation summary")
    print(f"Raw file: {args.raw_file}")
    print(f"Loaded records: {stats.loaded}")
    print(f"Saved records: {stats.saved}")
    print(f"Skipped records: {stats.skipped}")
    print("\nRecords by refactoring type:")
    for refactoring_type, count in stats.by_type.items():
        print(f"- {refactoring_type}: {count}")
    print("\nSplit counts:")
    for split, count in stats.split_counts.items():
        print(f"- {split}: {count}")
    print(f"\nAverage input length: {stats.avg_input_length:.2f}")
    print(f"Average output length: {stats.avg_output_length:.2f}")
    print(f"Output directory: {args.out_dir}")


if __name__ == "__main__":
    main()
