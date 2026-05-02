from __future__ import annotations

from llm_ontology.evaluation.metrics import aggregate_scores


def evaluate_refactoring(records: list[dict]) -> dict:
    scores = aggregate_scores(records)
    scores["domain"] = "refactoring"
    return scores
