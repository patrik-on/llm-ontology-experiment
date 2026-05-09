from __future__ import annotations

from pathlib import Path
from typing import Any


LEGACY_GENERATE_MESSAGE = """\
scripts/inference/generate.py is a legacy entrypoint for the removed experiment.yaml flow.

Use the current evaluation inference entrypoint instead, for example:

python scripts/evaluation/run_inference_eval.py ^
  --task testing ^
  --models-config configs/evaluation/eval_models.yaml ^
  --dataset data/processed/testing/test.jsonl ^
  --output evaluation/predictions/testing ^
  --model-name baseline_qwen25_coder_7b ^
  --limit 5 ^
  --overwrite

For full inference + metrics + report orchestration use:

python scripts/evaluation/run_full_evaluation.py --models-config configs/evaluation/eval_models.yaml --limit 100 --overwrite
"""


def generate_text(*args: Any, **kwargs: Any) -> str:
    raise RuntimeError(LEGACY_GENERATE_MESSAGE)


def generate_predictions(config: dict[str, Any]) -> Path:
    raise RuntimeError(LEGACY_GENERATE_MESSAGE)
