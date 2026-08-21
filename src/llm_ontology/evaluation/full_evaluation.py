from __future__ import annotations
import argparse
import subprocess
import sys

from llm_ontology.core.config import read_yaml
from llm_ontology.evaluation.run_layout import EvaluationRunLayout


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
    parser.add_argument(
        "--run-id",
        required=True,
        help="Stable run name under artifacts/evaluation/runs/.",
    )
    parser.add_argument("--skip-inference", action="store_true")
    parser.add_argument("--skip-metrics", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--testing-only", action="store_true")
    parser.add_argument("--refactoring-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()
    layout = EvaluationRunLayout(args.run_id)

    tasks = []
    if not args.refactoring_only:
        tasks.append(("testing", "data/processed/testing/test.jsonl"))
    if not args.testing_only:
        tasks.append(("refactoring", "data/processed/refactoring/test.jsonl"))

    model_names = selected_model_names(args.models_config, args.model_name)
    manifest_metadata = {
        "models_config": args.models_config,
        "models": model_names,
        "tasks": [task for task, _ in tasks],
        "limit": args.limit,
        "overwrite": args.overwrite,
    }
    layout.write_manifest(status="running", metadata=manifest_metadata)
    all_succeeded = True
    try:
        for task, dataset in tasks:
            pred_dir = str(layout.predictions / task)
            metrics_dir = str(layout.metrics / task)
            if not args.skip_inference:
                for current_model_name in model_names:
                    print(f"Running task={task}, model={current_model_name}")
                    cmd = [
                        sys.executable,
                        "scripts/evaluation/run_inference_eval.py",
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
                    all_succeeded &= run(
                        cmd,
                        continue_on_error=args.continue_on_error,
                    )
            if not args.skip_metrics:
                all_succeeded &= run(
                    [
                        sys.executable,
                        "scripts/evaluation/compute_eval_metrics.py",
                        "--task",
                        task,
                        "--predictions-dir",
                        pred_dir,
                        "--output-dir",
                        metrics_dir,
                    ],
                    continue_on_error=args.continue_on_error,
                )

        if not args.skip_report:
            all_succeeded &= run(
                [
                    sys.executable,
                    "scripts/evaluation/build_eval_report.py",
                    "--run-id",
                    layout.run_id,
                ],
                continue_on_error=args.continue_on_error,
            )
    except Exception:
        layout.write_manifest(status="failed")
        raise
    layout.write_manifest(
        status="completed" if all_succeeded else "completed_with_errors"
    )
    print(f"Evaluation artifacts: {layout.root}")


if __name__ == "__main__":
    main()
