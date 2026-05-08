from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.evaluation.prediction_io import write_jsonl


def main() -> None:
    root = Path("evaluation_smoke")
    if root.exists():
        shutil.rmtree(root)
    testing_dir = root / "predictions" / "testing"
    refactoring_dir = root / "predictions" / "refactoring"
    write_jsonl(
        [
            {
                "id": "test-1",
                "task": "testing",
                "model_name": "dummy_model",
                "source": "smoke",
                "domain": "testing",
                "input": "public int add(int a, int b) { return a + b; }",
                "expected_output": "@Test public void testAdd() { assertEquals(3, add(1, 2)); }",
                "prediction": "@Test public void testAdd() { assertEquals(3, add(1, 2)); }",
                "metadata": {},
                "generation_config": {},
            }
        ],
        testing_dir / "dummy_model.jsonl",
    )
    write_jsonl(
        [
            {
                "id": "ref-1",
                "task": "refactoring",
                "model_name": "dummy_model",
                "source": "smoke",
                "domain": "refactoring",
                "input": "class A { void m() { if (a && b) { doIt(); } } }",
                "expected_output": "class A { void m() { doItWhenReady(); } }",
                "prediction": "class A { void m() { doItWhenReady(); } }",
                "metadata": {},
                "generation_config": {},
            }
        ],
        refactoring_dir / "dummy_model.jsonl",
    )
    subprocess.run([sys.executable, "scripts/compute_eval_metrics.py", "--task", "testing", "--predictions-dir", str(testing_dir), "--output-dir", str(root / "metrics" / "testing")], check=True)
    subprocess.run([sys.executable, "scripts/compute_eval_metrics.py", "--task", "refactoring", "--predictions-dir", str(refactoring_dir), "--output-dir", str(root / "metrics" / "refactoring")], check=True)
    subprocess.run([sys.executable, "scripts/build_eval_report.py", "--output-root", str(root)], check=True)
    required = [
        root / "metrics" / "testing" / "aggregate_metrics.csv",
        root / "metrics" / "testing" / "aggregate_metrics.json",
        root / "metrics" / "refactoring" / "aggregate_metrics.csv",
        root / "metrics" / "refactoring" / "aggregate_metrics.json",
        root / "reports" / "evaluation_report.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Smoke eval failed, missing: {missing}")
    print("Smoke evaluation metrics check OK.")


if __name__ == "__main__":
    main()
