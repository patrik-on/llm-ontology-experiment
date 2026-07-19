from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.benchmarks import available_benchmarks, load_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and inventory vendored benchmarks.")
    parser.add_argument("--benchmark", choices=available_benchmarks(), help="Inspect only one benchmark.")
    parser.add_argument("--context-level", choices=("source", "simple", "full"), default="source")
    args = parser.parse_args()

    names = (args.benchmark,) if args.benchmark else available_benchmarks()
    for name in names:
        cases = load_benchmark(name, context_level=args.context_level)
        projects = Counter(str(case.metadata.get("project", "unknown")) for case in cases)
        references = sum(bool(case.reference_output.strip()) for case in cases)
        print(f"{name}: {len(cases)} cases, task={cases[0].task}, references={references}")
        print(f"  projects={dict(projects)}")


if __name__ == "__main__":
    main()
