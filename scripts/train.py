from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import load_experiment_config
from llm_ontology.core.logging import setup_logging
from llm_ontology.training.trainer import dry_run_training, train_from_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Train one fine-tuning experiment from YAML config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Validate config and output paths without training.")
    args = parser.parse_args()

    logger = setup_logging()
    config = load_experiment_config(args.config)
    if args.dry_run:
        logger.info("Dry run: %s", dry_run_training(config))
        return
    adapter_dir = train_from_config(config)
    logger.info("Saved adapter to %s.", adapter_dir)


if __name__ == "__main__":
    main()
