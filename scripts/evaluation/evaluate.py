from __future__ import annotations

import argparse


LEGACY_EVALUATE_MESSAGE = """\
scripts/evaluation/evaluate.py is a legacy entrypoint for the removed experiment.yaml flow.

Use the current evaluation pipeline instead:

1. Run inference:
python scripts/evaluation/run_inference_eval.py ^
  --task testing ^
  --models-config configs/evaluation/eval_models.yaml ^
  --dataset data/processed/testing/test.jsonl ^
  --output evaluation/predictions/testing ^
  --model-name baseline_qwen25_coder_7b ^
  --limit 5 ^
  --overwrite

2. Compute metrics:
python scripts/evaluation/compute_eval_metrics.py ^
  --task testing ^
  --predictions-dir evaluation/predictions/testing ^
  --output-dir evaluation/metrics/testing

3. Build report:
python scripts/evaluation/build_eval_report.py --output-root evaluation

For all three steps use:

python scripts/evaluation/run_full_evaluation.py --models-config configs/evaluation/eval_models.yaml --limit 100 --overwrite
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legacy compatibility wrapper. Use run_inference_eval.py, compute_eval_metrics.py, or run_full_evaluation.py instead."
    )
    parser.add_argument("--config", default=None, help="Legacy experiment config path; no longer supported.")
    parser.parse_args()
    raise SystemExit(LEGACY_EVALUATE_MESSAGE)


if __name__ == "__main__":
    main()
