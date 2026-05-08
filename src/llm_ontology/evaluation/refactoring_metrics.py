from __future__ import annotations

from typing import Any

from llm_ontology.evaluation.code_metrics import cohesion_proxy_score, compute_code_metrics, coupling_proxy_score
from llm_ontology.evaluation.text_metrics import basic_text_metrics, normalized_edit_similarity


def code_health_delta_score(input_metrics: dict[str, Any], prediction_metrics: dict[str, Any], output_non_empty: bool, differs: bool) -> float:
    if not output_non_empty:
        return 0.0
    score = 5.0
    complexity_delta = float(prediction_metrics.get("complexity_proxy_score", 0)) - float(input_metrics.get("complexity_proxy_score", 0))
    nesting_delta = float(prediction_metrics.get("max_brace_nesting_depth", 0)) - float(input_metrics.get("max_brace_nesting_depth", 0))
    avg_method_delta = float(prediction_metrics.get("avg_method_length_proxy", 0)) - float(input_metrics.get("avg_method_length_proxy", 0))
    if complexity_delta < 0:
        score += 1.5
    elif complexity_delta > 3:
        score -= 2.0
    if nesting_delta < 0:
        score += 1.0
    elif nesting_delta > 1:
        score -= 1.0
    if avg_method_delta < 0:
        score += 1.0
    elif avg_method_delta > 20:
        score -= 1.0
    if differs:
        score += 1.0
    else:
        score -= 2.0
    return max(0.0, min(10.0, score))


def refactoring_quality_score(metrics: dict[str, Any]) -> float:
    if not metrics["output_non_empty"]:
        return 0.0
    score = 0.0
    score += 1.5 if metrics["output_differs_from_input"] else 0.0
    score += float(metrics["normalized_edit_similarity_to_expected"]) * 2.5
    score += float(metrics["code_health_delta_score"]) * 0.25
    score += float(metrics["cohesion_proxy_score"]) * 0.2
    score += max(0.0, 10.0 - float(metrics["coupling_proxy_score"])) * 0.15
    return max(0.0, min(10.0, score))


def compute_refactoring_metrics(record: dict[str, Any]) -> dict[str, Any]:
    input_text = str(record.get("input", ""))
    expected_output = str(record.get("expected_output", ""))
    prediction = str(record.get("prediction", ""))
    text = basic_text_metrics(input_text, expected_output, prediction)
    input_metrics = compute_code_metrics(input_text)
    expected_metrics = compute_code_metrics(expected_output)
    prediction_metrics = compute_code_metrics(prediction)
    predicted_complexity_delta = float(prediction_metrics.get("complexity_proxy_score", 0)) - float(input_metrics.get("complexity_proxy_score", 0))
    expected_complexity_delta = float(expected_metrics.get("complexity_proxy_score", 0)) - float(input_metrics.get("complexity_proxy_score", 0))
    metrics: dict[str, Any] = {
        **text,
        "normalized_edit_similarity_to_expected": normalized_edit_similarity(expected_output, prediction),
        "input_code_metrics": input_metrics,
        "expected_code_metrics": expected_metrics,
        "prediction_code_metrics": prediction_metrics,
        "predicted_complexity_delta": predicted_complexity_delta,
        "expected_complexity_delta": expected_complexity_delta,
        "predicted_loc_delta": int(prediction_metrics.get("lines_of_code", 0)) - int(input_metrics.get("lines_of_code", 0)),
        "predicted_avg_method_length_delta": float(prediction_metrics.get("avg_method_length_proxy", 0)) - float(input_metrics.get("avg_method_length_proxy", 0)),
        "predicted_max_nesting_delta": int(prediction_metrics.get("max_brace_nesting_depth", 0)) - int(input_metrics.get("max_brace_nesting_depth", 0)),
        "cohesion_proxy_score": cohesion_proxy_score(prediction_metrics),
        "coupling_proxy_score": coupling_proxy_score(prediction_metrics),
    }
    metrics["code_health_delta_score"] = code_health_delta_score(
        input_metrics,
        prediction_metrics,
        bool(metrics["output_non_empty"]),
        bool(metrics["output_differs_from_input"]),
    )
    metrics["refactoring_quality_score"] = refactoring_quality_score(metrics)
    return metrics
