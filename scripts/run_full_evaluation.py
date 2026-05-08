from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import read_yaml


def run(cmd: list[str], continue_on_error: bool = False) -> bool:
    print(" ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        return True
    if continue_on_error:
        print(f"[WARN] Command failed with exit code {result.returncode}; continuing because --continue-on-error is set.")
        return False
    raise subprocess.CalledProcessError(result.returncode, cmd)


def selected_model_names(models_config_path: str, model_name: str | None) -> list[str]:
    config = read_yaml(models_config_path)
    names = [str(model["name"]) for model in config.get("models", [])]
    if model_name:
        if model_name not in names:
            raise ValueError(f"Model not found in {models_config_path}: {model_name}")
        return [model_name]
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full evaluation: inference, metrics, report.")
    parser.add_argument("--models-config", default="configs/evaluation/eval_models.yaml")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-root", default="evaluation")
    parser.add_argument("--skip-inference", action="store_true")
    parser.add_argument("--skip-metrics", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--testing-only", action="store_true")
    parser.add_argument("--refactoring-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    tasks = []
    if not args.refactoring_only:
        tasks.append(("testing", "data/processed/testing/test.jsonl"))
    if not args.testing_only:
        tasks.append(("refactoring", "data/processed/refactoring/test.jsonl"))

    model_names = selected_model_names(args.models_config, args.model_name)

    for task, dataset in tasks:
        pred_dir = str(Path(args.output_root) / "predictions" / task)
        metrics_dir = str(Path(args.output_root) / "metrics" / task)
        if not args.skip_inference:
            for current_model_name in model_names:
                print(f"Running task={task}, model={current_model_name}")
                cmd = [
                    sys.executable,
                    "scripts/run_inference_eval.py",
                    "--task",
                    task,
                    "--models-config",
                    args.models_config,
                    "--dataset",
                    dataset,
                    "--output",
                    pred_dir,
                    "--model-name",
                    current_model_name,
                ]
                if args.limit is not None:
                    cmd += ["--limit", str(args.limit)]
                if args.overwrite:
                    cmd.append("--overwrite")
                run(cmd, continue_on_error=args.continue_on_error)
        if not args.skip_metrics:
            run([sys.executable, "scripts/compute_eval_metrics.py", "--task", task, "--predictions-dir", pred_dir, "--output-dir", metrics_dir])

    if not args.skip_report:
        run([sys.executable, "scripts/build_eval_report.py", "--output-root", args.output_root])


if __name__ == "__main__":
    main()
