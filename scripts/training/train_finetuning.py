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
    args = parser.parse_args()
    run_training(args.config, resume_from_checkpoint=args.resume_from_checkpoint)


if __name__ == "__main__":
    main()
