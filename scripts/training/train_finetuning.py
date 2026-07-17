from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.training.finetuning import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LoRA/QLoRA fine-tuning from a YAML config.")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--resume_from_checkpoint",
        type=str,
        default=None,
        help="Optional path to a Trainer checkpoint directory to resume training from.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Use configured sample limits for a short validation run.")
    parser.add_argument("--max_steps", type=int, default=None, help="Override run.max_steps, e.g. 2 for a smoke run.")
    parser.add_argument("--max_train_samples", type=int, default=None, help="Override run.max_train_samples.")
    parser.add_argument("--max_val_samples", type=int, default=None, help="Override run.max_val_samples.")
    parser.add_argument("--seed", type=int, default=None, help="Override run.seed.")
    parser.add_argument(
        "--output-root",
        default=None,
        help="Write checkpoints/logs/results under this root instead of the configured experiment output paths.",
    )
    args = parser.parse_args()
    run_training(
        args.config,
        resume_from_checkpoint=args.resume_from_checkpoint,
        dry_run=args.dry_run,
        max_steps=args.max_steps,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        seed=args.seed,
        output_root=args.output_root,
    )


if __name__ == "__main__":
    main()
