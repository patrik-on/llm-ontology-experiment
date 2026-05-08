# Fine-Tuning Design

All experiments use the same Python entry points and differ only through YAML configuration.

- `scripts/data/prepare_data.py` prepares `train.jsonl`, `val.jsonl`, and `test.jsonl`.
- `scripts/training/train_finetuning.py --config <training.yaml>` trains a LoRA or QLoRA adapter.
- `scripts/inference/generate.py --config <experiment.yaml>` writes `predictions.jsonl`.
- `scripts/evaluation/evaluate.py --config <experiment.yaml>` writes `metrics.json` and `report.md`.

Large outputs belong in `artifacts/`; small experiment outputs belong in `results/`.

