"""Validate datasets, configs, models, and outputs before fine-tuning."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.training.readiness import main


if __name__ == "__main__":
    main()
