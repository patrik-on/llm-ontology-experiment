"""Mixed SWE/MaRV/ML4Ref refactoring matrix, using the existing WSL environment."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from llm_ontology.benchmarks.refactoring_matrix import main

if __name__ == "__main__":
    raise SystemExit(main())
