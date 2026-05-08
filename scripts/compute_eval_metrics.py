from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.evaluation.prediction_io import normalize_prediction_record, read_jsonl, write_csv, write_json, write_jsonl
from llm_ontology.evaluation.refactoring_metrics import compute_refactoring_metrics
from llm_ontology.evaluation.test_metrics import compute_testing_metrics


def numeric(values: list[Any]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float, bool))]


def avg(items: list[dict[str, Any]], key: str) -> float:
    values = numeric([item.get(key) for item in items])
    return mean(values) if values else 0.0


def med(items: list[dict[str, Any]], key: str) -> float:
    values = numeric([item.get(key) for item in items])
    return median(values) if values else 0.0


def aggregate_testing(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(items),
        "output_non_empty_rate": avg(items, "output_non_empty"),
        "contains_test_annotation_rate": avg(items, "contains_test_annotation"),
        "has_assertion_rate": avg(items, "has_assertion"),
        "target_method_invocation_rate": avg(items, "target_method_invocation_proxy"),
        "trivial_test_smell_rate": avg(items, "trivial_test_smell"),
        "avg_test_quality_score": avg(items, "generated_test_quality_score"),
        "median_test_quality_score": med(items, "generated_test_quality_score"),
        "min_test_quality_score": min(numeric([item.get("generated_test_quality_score") for item in items]), default=0.0),
        "max_test_quality_score": max(numeric([item.get("generated_test_quality_score") for item in items]), default=0.0),
        "avg_coverage_proxy_score": avg(items, "coverage_proxy_score"),
    }


def aggregate_refactoring(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(items),
        "output_non_empty_rate": avg(items, "output_non_empty"),
        "output_differs_from_input_rate": avg(items, "output_differs_from_input"),
        "avg_edit_similarity": avg(items, "normalized_edit_similarity_to_expected"),
        "avg_code_health_delta_score": avg(items, "code_health_delta_score"),
        "avg_cohesion_proxy_score": avg(items, "cohesion_proxy_score"),
        "avg_coupling_proxy_score": avg(items, "coupling_proxy_score"),
        "avg_refactoring_quality_score": avg(items, "refactoring_quality_score"),
        "median_refactoring_quality_score": med(items, "refactoring_quality_score"),
        "min_refactoring_quality_score": min(numeric([item.get("refactoring_quality_score") for item in items]), default=0.0),
        "max_refactoring_quality_score": max(numeric([item.get("refactoring_quality_score") for item in items]), default=0.0),
        "avg_complexity_delta": avg(items, "predicted_complexity_delta"),
        "avg_loc_delta": avg(items, "predicted_loc_delta"),
    }


def compute_metrics(task: str, predictions_dir: str | Path, output_dir: str | Path) -> None:
    per_examples: list[dict[str, Any]] = []
    for path in sorted(Path(predictions_dir).glob("*.jsonl")):
        for index, raw in enumerate(read_jsonl(path)):
            record = normalize_prediction_record(raw, task, str(raw.get("model_name") or path.stem), index)
            metrics = compute_testing_metrics(record) if task == "testing" else compute_refactoring_metrics(record)
            per_examples.append({**record, **metrics})

    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in per_examples:
        by_model[item["model_name"]].append(item)
    aggregates = []
    for model_name, items in sorted(by_model.items()):
        payload = aggregate_testing(items) if task == "testing" else aggregate_refactoring(items)
        aggregates.append({"model_name": model_name, **payload})

    output = Path(output_dir)
    write_jsonl(per_examples, output / "per_example_metrics.jsonl")
    write_csv(per_examples, output / "per_example_metrics.csv")
    write_json(aggregates, output / "aggregate_metrics.json")
    write_csv(aggregates, output / "aggregate_metrics.csv")
    print(f"Wrote metrics to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute evaluation metrics from prediction JSONL files.")
    parser.add_argument("--task", required=True, choices=("testing", "refactoring"))
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    compute_metrics(args.task, args.predictions_dir, args.output_dir)


if __name__ == "__main__":
    main()
