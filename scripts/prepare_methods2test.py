from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.methods2test import ALLOWED_CONTEXT_FIELDS, SUBSET_SIZES, prepare_methods2test


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a small Methods2Test instruction-tuning subset.")
    parser.add_argument("--raw-dir", default="data/raw/methods2test/corpus/json")
    parser.add_argument("--out-dir", default="data/processed/testing")
    parser.add_argument("--context-field", default="src_fm", choices=ALLOWED_CONTEXT_FIELDS)
    parser.add_argument("--train-size", type=int, default=SUBSET_SIZES["train"])
    parser.add_argument("--val-size", type=int, default=SUBSET_SIZES["eval"])
    parser.add_argument("--test-size", type=int, default=SUBSET_SIZES["test"])
    parser.add_argument("--seed", type=int, default=42, help="Reserved for future sampling; official split order is kept.")
    args = parser.parse_args()

    stats = prepare_methods2test(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        context_field=args.context_field,
        subset_sizes={"train": args.train_size, "eval": args.val_size, "test": args.test_size},
    )

    print("Methods2Test preparation summary")
    print(f"Raw dir: {args.raw_dir}")
    print(f"Context field: {args.context_field}")
    for item in stats:
        print(f"\nSplit: {item.split}")
        print(f"Loaded files: {item.loaded}")
        print(f"Saved examples: {item.saved}")
        print(f"Skipped examples: {item.skipped}")
        print(f"Average input length: {item.avg_input_length:.2f}")
        print(f"Average output length: {item.avg_output_length:.2f}")
        print(f"Output path: {item.output_path}")


if __name__ == "__main__":
    main()
