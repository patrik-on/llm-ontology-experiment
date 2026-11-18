"""Build eval-aligned (v3) fine-tuning datasets. See docs/finetuning/v3_runbook.md.

Run from the repository root in WSL with the evaluation environment (tree-sitter,
transformers for --max-seq-length, JDK + RefactoringMiner tools for `refactoring`).
No model calls, no index or evaluation-run writes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.datasets import eval_aligned_v3 as v3


def fits_from(args):
    if not args.max_seq_length:
        return None
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True, local_files_only=True)
    return v3.token_fit(tokenizer, args.max_seq_length)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["testing", "refactoring", "combined"])
    parser.add_argument("--out-root", default="data/processed/v3")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tokenizer", default="/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--max-seq-length", type=int, default=8192,
                        help="Drop (never truncate) records longer than this; 0 disables the check.")
    parser.add_argument("--methods2test-archive", default="data/raw/methods2test/dataset/train.tar.bz2")
    parser.add_argument("--testing-train", type=int, default=4000)
    parser.add_argument("--testing-val", type=int, default=500)
    parser.add_argument("--project-cap", type=int, default=20)
    parser.add_argument("--max-records", type=int, default=None, help="Stop the archive scan early (smoke runs).")
    parser.add_argument("--plan", default="configs/benchmarks/refactoring_matrix_v1.json",
                        help="Refactoring matrix plan: cohort manifest + RefactoringMiner tool paths.")
    parser.add_argument("--work-dir", default="artifacts/finetuning/v3-refactoring-discovery")
    parser.add_argument("--refactoring-train", type=int, default=4000)
    parser.add_argument("--refactoring-val", type=int, default=500)
    parser.add_argument("--per-type", type=int, default=400)
    parser.add_argument("--max-archives", type=int, default=None)
    args = parser.parse_args()

    out_root = ROOT / args.out_root
    if args.task == "testing":
        report = v3.build_testing_v3(ROOT / args.methods2test_archive, out_root / "testing",
                                     train_size=args.testing_train, val_size=args.testing_val,
                                     project_cap=args.project_cap, seed=args.seed,
                                     max_records=args.max_records, fits=fits_from(args))
    elif args.task == "refactoring":
        plan = json.loads((ROOT / args.plan).read_text())
        report = v3.build_refactoring_v3(ROOT, Path(plan["raw_ml4refactoring"]), ROOT / args.work_dir,
                                         out_root / "refactoring", plan=plan,
                                         train_size=args.refactoring_train, val_size=args.refactoring_val,
                                         per_type=args.per_type, max_archives=args.max_archives,
                                         seed=args.seed, fits=fits_from(args))
    else:
        report = v3.build_combined_v3(out_root / "testing", out_root / "refactoring",
                                      out_root / "combined", seed=args.seed)
    print(json.dumps(report, indent=2, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
