# Fine-Tuning Design

All experiments use the same Python entry points and differ only through YAML configuration.

- `scripts/data/prepare_data.py` prepares `train.jsonl`, `val.jsonl`, and `test.jsonl`.
- `scripts/training/train_finetuning.py --config <training.yaml>` trains a LoRA or QLoRA adapter.
- `scripts/evaluation/run_inference_eval.py --task <testing|refactoring> ...` writes model prediction JSONL files.
- `scripts/evaluation/compute_eval_metrics.py --task <testing|refactoring> ...` writes per-example and aggregate metrics.
- `scripts/evaluation/build_eval_report.py --output-root evaluation` writes the Markdown report.
- `scripts/evaluation/run_full_evaluation.py ...` orchestrates inference, metrics, and report generation.

The old `scripts/inference/generate.py --config <experiment.yaml>` and `scripts/evaluation/evaluate.py --config <experiment.yaml>` flow has been retired. Those files remain only as compatibility wrappers that point to the current evaluation pipeline.

Large outputs belong in `artifacts/`; small experiment outputs belong in `results/`.

