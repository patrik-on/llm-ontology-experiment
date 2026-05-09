from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.inference.generate import LEGACY_GENERATE_MESSAGE


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legacy compatibility wrapper. Use scripts/evaluation/run_inference_eval.py instead."
    )
    parser.add_argument("--config", default=None, help="Legacy experiment config path; no longer supported.")
    parser.parse_args()
    raise SystemExit(LEGACY_GENERATE_MESSAGE)


if __name__ == "__main__":
    main()
