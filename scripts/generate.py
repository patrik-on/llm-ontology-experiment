from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import load_experiment_config
from llm_ontology.core.logging import setup_logging
from llm_ontology.inference.generate import generate_predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate predictions for one experiment config.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    logger = setup_logging()
    config = load_experiment_config(args.config)
    predictions_path = generate_predictions(config)
    logger.info("Saved predictions to %s.", predictions_path)


if __name__ == "__main__":
    main()
