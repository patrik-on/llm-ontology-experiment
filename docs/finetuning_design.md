# Fine-Tuning Design

All experiments use the same Python entry points and differ only through YAML configuration.

- `scripts/prepare_data.py` prepares `train.jsonl`, `val.jsonl`, and `test.jsonl`.
- `scripts/train.py --config <experiment.yaml>` trains a LoRA or QLoRA adapter.
- `scripts/generate.py --config <experiment.yaml>` writes `predictions.jsonl`.
- `scripts/evaluate.py --config <experiment.yaml>` writes `metrics.json` and `report.md`.

Large outputs belong in `artifacts/`; small experiment outputs belong in `results/`.
