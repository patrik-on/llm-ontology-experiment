from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.evaluation.report_writer import write_evaluation_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Markdown evaluation report from aggregate metrics.")
    parser.add_argument("--output-root", default="evaluation")
    args = parser.parse_args()
    path = write_evaluation_report(args.output_root)
    print(f"Wrote report: {path}")


if __name__ == "__main__":
    main()
