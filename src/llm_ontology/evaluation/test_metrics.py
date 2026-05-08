from __future__ import annotations

import re
from typing import Any

from llm_ontology.evaluation.text_metrics import basic_text_metrics


ASSERTION_PATTERNS = (
    "assertEquals",
    "assertTrue",
    "assertFalse",
    "assertNull",
    "assertNotNull",
    "assertThrows",
    "assertThat",
    "verify",
)


def infer_target_method(input_text: str, metadata: dict[str, Any] | None = None) -> str | None:
    metadata = metadata or {}
    for key in ("target_method", "method_name", "focal_method_name"):
        value = metadata.get(key)
        if value:
            return str(value)
    match = re.search(r"(?:public|private|protected|static|\s)+[\w<>\[\], ?]+\s+(\w+)\s*\(", input_text or "")
    return match.group(1) if match else None


def trivial_test_smell(prediction: str) -> bool:
    text = prediction or ""
    stripped = text.strip()
    if not stripped:
        return True
    if re.fullmatch(r"(?s)(//.*|\s|/\*.*\*/)*", stripped):
        return True
    smell_patterns = (r"assertTrue\s*\(\s*true\s*\)", r"true\s*==\s*true", r"assertEquals\s*\(\s*1\s*,\s*1\s*\)")
    return any(re.search(pattern, text) for pattern in smell_patterns)


def generated_test_quality_score(metrics: dict[str, Any]) -> float:
    score = 0.0
    if metrics["output_non_empty"]:
        score += 1.0
    if metrics["contains_test_annotation"]:
        score += 2.0
    if metrics["has_assertion"]:
        score += 2.0
    if metrics["target_method_invocation_proxy"]:
        score += 2.0
    if metrics["has_exception_test"]:
        score += 1.0
    if metrics["assertion_count"] > 1 or metrics["test_method_count_proxy"] > 1:
        score += 1.0
    if metrics["trivial_test_smell"]:
        score -= 3.0
    if not metrics["output_non_empty"]:
        score -= 5.0
    return max(0.0, min(10.0, score))


def coverage_proxy_label(score: float) -> str:
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "invalid"


def compute_testing_metrics(record: dict[str, Any]) -> dict[str, Any]:
    input_text = str(record.get("input", ""))
    expected_output = str(record.get("expected_output", ""))
    prediction = str(record.get("prediction", ""))
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    target_method = infer_target_method(input_text, metadata)
    assertion_count = sum(len(re.findall(pattern + r"\s*\(", prediction)) for pattern in ASSERTION_PATTERNS)
    metrics: dict[str, Any] = {
        **basic_text_metrics(input_text, expected_output, prediction),
        "contains_test_annotation": "@Test" in prediction,
        "test_method_count_proxy": len(re.findall(r"@Test|void\s+\w+\s*\(", prediction)),
        "assertion_count": assertion_count,
        "has_assertion": assertion_count > 0,
        "has_exception_test": bool(re.search(r"assertThrows|expected\s*=|try\s*\{|catch\s*\(|\bthrows\b", prediction)),
        "has_mocking": bool(re.search(r"Mockito|mock\s*\(|when\s*\(|verify\s*\(", prediction)),
        "target_method": target_method,
        "target_method_invocation_proxy": bool(target_method and re.search(rf"\b{re.escape(target_method)}\s*\(", prediction)),
        "trivial_test_smell": trivial_test_smell(prediction),
    }
    score = generated_test_quality_score(metrics)
    metrics["generated_test_quality_score"] = score
    metrics["coverage_proxy_score"] = score
    metrics["coverage_proxy_label"] = coverage_proxy_label(score)
    return metrics
