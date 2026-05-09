from __future__ import annotations

import subprocess
import sys


def run_script(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, path],
        text=True,
        capture_output=True,
        check=False,
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def test_legacy_generate_points_to_current_entrypoint() -> None:
    result = run_script("scripts/inference/generate.py")
    output = combined_output(result)

    assert result.returncode != 0
    assert "legacy entrypoint" in output
    assert "run_inference_eval.py" in output


def test_legacy_evaluate_points_to_current_pipeline() -> None:
    result = run_script("scripts/evaluation/evaluate.py")
    output = combined_output(result)

    assert result.returncode != 0
    assert "legacy entrypoint" in output
    assert "run_full_evaluation.py" in output
