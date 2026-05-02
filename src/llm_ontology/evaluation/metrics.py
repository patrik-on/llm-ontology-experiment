from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_predictions(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def exact_match(reference: str, prediction: str) -> float:
    return float(reference.strip() == prediction.strip())


def token_f1(reference: str, prediction: str) -> float:
    ref_tokens = reference.split()
    pred_tokens = prediction.split()
    if not ref_tokens and not pred_tokens:
        return 1.0
    if not ref_tokens or not pred_tokens:
        return 0.0
    overlap = len(set(ref_tokens) & set(pred_tokens))
    precision = overlap / len(set(pred_tokens))
    recall = overlap / len(set(ref_tokens))
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def aggregate_scores(records: list[dict[str, Any]]) -> dict[str, float | int]:
    if not records:
        return {"count": 0, "exact_match": 0.0, "token_f1": 0.0}
    em = [exact_match(record["reference"], record["prediction"]) for record in records]
    f1 = [token_f1(record["reference"], record["prediction"]) for record in records]
    return {
        "count": len(records),
        "exact_match": sum(em) / len(em),
        "token_f1": sum(f1) / len(f1),
    }
