"""C/D1/D2 repair-loop pilot (third runner), using the existing WSL environment."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from llm_ontology.repair.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
