from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.ml4refactoring import (
    DEFAULT_DATASET_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_TEMP_DIR,
    prepare_ml4refactoring_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare ML4Refactoring instruction-tuning JSONL subset.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--temp-dir", default=str(DEFAULT_TEMP_DIR))
    parser.add_argument("--train-size", type=int, default=4000)
    parser.add_argument("--val-size", type=int, default=500)
    parser.add_argument("--test-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-input-chars", type=int, default=12000)
    parser.add_argument("--max-output-chars", type=int, default=12000)
    parser.add_argument("--max-projects", type=int, default=None)
    parser.add_argument("--max-total", type=int, default=None)
    args = parser.parse_args()

    max_total = args.max_total
    if max_total is None:
        max_total = args.train_size + args.val_size + args.test_size

    stats = prepare_ml4refactoring_dataset(
        dataset_dir=args.dataset_dir,
        output_dir=args.out_dir,
        temp_dir=args.temp_dir,
        train_size=args.train_size,
        val_size=args.val_size,
        test_size=args.test_size,
        seed=args.seed,
        max_input_chars=args.max_input_chars,
        max_output_chars=args.max_output_chars,
        max_projects=args.max_projects,
        max_total=max_total,
        progress=True,
    )

    print("\nML4Refactoring preparation summary")
    print(f"Dataset directory: {args.dataset_dir}")
    print(f"Output directory: {stats.output_dir}")
    print(f"Processed project ZIPs: {stats.processed_project_zips}")
    print(f"Skipped projects: {stats.skipped_projects}")
    print(f"Commit directories: {stats.commits}")
    print(f"Candidate before/after pairs: {stats.candidate_pairs}")
    print(f"Valid saved examples: {stats.saved}")
    print(f"Skipped examples: {stats.skipped_examples}")

    print("\nExamples by refactoring type:")
    for refactoring_type, count in sorted(stats.by_type.items()):
        print(f"- {refactoring_type}: {count}")

    print("\nSplit counts:")
    for split, count in stats.split_counts.items():
        print(f"- {split}: {count}")

    print(f"\nAverage input length: {stats.avg_input_length:.2f}")
    print(f"Average output length: {stats.avg_output_length:.2f}")


if __name__ == "__main__":
    main()
