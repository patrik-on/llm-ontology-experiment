# Fine-Tuning Design

All experiments use the same Python entry points and differ only through YAML configuration.

- `scripts/datasets/prepare_data.py` prepares `train.jsonl`, `val.jsonl`, and `test.jsonl`.
- `scripts/finetuning/train_finetuning.py --config <training.yaml>` trains a LoRA or QLoRA adapter.


All evaluation outputs belong in `artifacts/evaluation/runs/<run_id>/`; a
validated run ID prevents new evaluation directories from appearing at the
repository root.

Evaluation entry points are documented in [current evaluation](../evaluation/README.md). Training/retrieval utilities do not define additional evaluation protocols.
