"""Forward context-eval commands to the independent sibling repository."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVAL_REPO = Path(os.environ.get("SI_CONTEXT_EVAL_REPO", PROJECT_ROOT.parent / "si-context-eval")).resolve()


def main() -> int:
    if not (EVAL_REPO / "evaluation" / "cli.py").is_file():
        raise SystemExit(f"SI context eval repository not found: {EVAL_REPO}")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(EVAL_REPO) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.call([sys.executable, "-m", "evaluation.cli", *sys.argv[1:]],
                           cwd=EVAL_REPO, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
