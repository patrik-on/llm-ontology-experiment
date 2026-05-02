from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import load_experiment_config
from llm_ontology.core.logging import setup_logging
from llm_ontology.evaluation.report import evaluate_predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate predictions for one experiment config.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    logger = setup_logging()
    config = load_experiment_config(args.config)
    metrics_path, report_path = evaluate_predictions(config)
    logger.info("Saved metrics to %s and report to %s.", metrics_path, report_path)


if __name__ == "__main__":
    main()
