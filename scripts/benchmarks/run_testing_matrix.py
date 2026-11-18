"""Run from any working directory using the project's WSL Python environment."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from llm_ontology.benchmarks.testing_matrix import main

if __name__ == "__main__":
    raise SystemExit(main())
