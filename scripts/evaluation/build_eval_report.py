"""Build the canonical human-readable evaluation report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.evaluation.report_writer import write_evaluation_report
from llm_ontology.evaluation.run_layout import EvaluationRunLayout


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Markdown evaluation report from aggregate metrics.")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    layout = EvaluationRunLayout(args.run_id)
    path = write_evaluation_report(layout.root)
    print(f"Wrote report: {path}")


if __name__ == "__main__":
    main()
