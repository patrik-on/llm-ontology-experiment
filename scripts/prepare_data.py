from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import load_config
from llm_ontology.core.logging import setup_logging
from llm_ontology.core.paths import resolve_path
from llm_ontology.data.download import list_data_files
from llm_ontology.data.format import load_domain_records, write_jsonl
from llm_ontology.data.split import combine_records, split_records


def write_split(records: list[dict], output_dir: Path, seed: int) -> None:
    train, val, test = split_records(records, seed=seed) if records else ([], [], [])
    write_jsonl(train, output_dir / "train.jsonl")
    write_jsonl(val, output_dir / "val.jsonl")
    write_jsonl(test, output_dir / "test.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare MaRV, Methods2Test, and combined JSONL datasets.")
    parser.add_argument("--config", default="configs/base.yaml")
    args = parser.parse_args()

    logger = setup_logging()
    config = load_config(args.config)
    seed = int(config.get("training", {}).get("seed", 42))
    paths = config["paths"]

    refactoring_files = list_data_files(resolve_path(paths["raw_refactoring_dir"]))
    testing_files = list_data_files(resolve_path(paths["raw_testing_dir"]))
    refactoring_records = load_domain_records(refactoring_files, "refactoring") if refactoring_files else []
    testing_records = load_domain_records(testing_files, "testing") if testing_files else []

    if not refactoring_records:
        logger.warning("No refactoring records prepared. Add raw MaRV data to %s.", paths["raw_refactoring_dir"])
    if not testing_records:
        logger.warning("No testing records prepared. Add raw Methods2Test data to %s.", paths["raw_testing_dir"])

    processed_dir = resolve_path(paths["processed_dir"])
    write_split(refactoring_records, processed_dir / "refactoring", seed)
    write_split(testing_records, processed_dir / "testing", seed)
    write_split(combine_records(refactoring_records, testing_records), processed_dir / "combined", seed)
    logger.info("Prepared datasets under %s.", processed_dir)


if __name__ == "__main__":
    main()
