from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from llm_ontology.evaluation.prediction_io import read_jsonl


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def score(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def best_model(aggregates: list[dict[str, Any]], metric: str, lower_is_better: bool = False) -> str:
    values = [item for item in aggregates if item.get(metric) is not None]
    if not values:
        return "n/a"
    key = lambda item: float(item.get(metric, 0))
    return str((min if lower_is_better else max)(values, key=key).get("model_name"))


def load_aggregate(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("models", [])


def write_examples(task: str, predictions_dir: Path, metrics_path: Path, output_path: Path, limit: int = 6) -> None:
    metrics = read_jsonl(metrics_path) if metrics_path.exists() else []
    by_key = {(item["model_name"], item["id"]): item for item in metrics}
    lines = [f"# {task.title()} Qualitative Examples", ""]
    count = 0
    for pred_path in sorted(predictions_dir.glob("*.jsonl")):
        for record in read_jsonl(pred_path)[:2]:
            metric = by_key.get((record.get("model_name"), record.get("id")), {})
            lines.extend(
                [
                    f"## {record.get('model_name')} / {record.get('id')}",
                    "",
                    "### Input",
                    "```java",
                    str(record.get("input", ""))[:2000],
                    "```",
                    "",
                    "### Expected Output",
                    "```java",
                    str(record.get("expected_output", ""))[:2000],
                    "```",
                    "",
                    "### Prediction",
                    "```java",
                    str(record.get("prediction", ""))[:2000],
                    "```",
                    "",
                    "### Metrics",
                    "```json",
                    __import__("json").dumps(metric, ensure_ascii=False, indent=2)[:2000],
                    "```",
                    "",
                ]
            )
            count += 1
            if count >= limit:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("\n".join(lines), encoding="utf-8")
                return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_evaluation_report(output_root: str | Path = "evaluation") -> Path:
    root = Path(output_root)
    testing = load_aggregate(root / "metrics" / "testing" / "aggregate_metrics.json")
    refactoring = load_aggregate(root / "metrics" / "refactoring" / "aggregate_metrics.json")
    report_path = root / "reports" / "evaluation_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    testing_rows = [
        [
            item["model_name"],
            pct(item.get("output_non_empty_rate")),
            pct(item.get("contains_test_annotation_rate")),
            pct(item.get("has_assertion_rate")),
            pct(item.get("target_method_invocation_rate")),
            pct(item.get("trivial_test_smell_rate")),
            score(item.get("avg_test_quality_score")),
            score(item.get("avg_coverage_proxy_score")),
        ]
        for item in testing
    ]
    refactoring_rows = [
        [
            item["model_name"],
            pct(item.get("output_non_empty_rate")),
            pct(item.get("output_differs_from_input_rate")),
            score(item.get("avg_edit_similarity")),
            score(item.get("avg_code_health_delta_score")),
            score(item.get("avg_cohesion_proxy_score")),
            score(item.get("avg_coupling_proxy_score")),
            score(item.get("avg_refactoring_quality_score")),
        ]
        for item in refactoring
    ]

    best_testing = best_model(testing, "avg_test_quality_score")
    best_refactoring = best_model(refactoring, "avg_refactoring_quality_score")
    b1_testing = next((item for item in testing if item.get("model_name") == "b1_shared"), None)
    b1_refactoring = next((item for item in refactoring if item.get("model_name") == "b1_shared"), None)
    b1_note = "B1 shared was evaluated on both tasks." if b1_testing and b1_refactoring else "B1 shared is missing from at least one task aggregate."

    lines = [
        "# Evaluation Report: LLM Ontology Experiment",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Evaluated Models",
        "",
        "- baseline_qwen25_coder_7b",
        "- b2_testing",
        "- b2_refactoring",
        "- b1_shared",
        "",
        "## Evaluated Datasets",
        "",
        "- testing test split",
        "- refactoring test split",
        "",
        "## Methodology",
        "",
        "Inference uses the local Qwen2.5-Coder-7B-Instruct base model with optional PEFT LoRA adapters. Decoding defaults to deterministic generation unless overridden in the evaluation config. The pipeline supports limiting the number of examples for pilot runs.",
        "",
        "Testing coverage is reported as a proxy score based on generated test structure, assertions, target-method invocation and trivial-test smells. Refactoring code health, cohesion and coupling are proxy metrics based on text-level Java-like code analysis. These proxy metrics do not replace real JaCoCo coverage, full Java parsing, manual review or executable project-level validation.",
        "",
        "## Testing Results",
        "",
        markdown_table(
            ["Model", "Non-empty", "@Test rate", "Assertion rate", "Target call rate", "Trivial smell rate", "Avg test quality", "Avg coverage proxy"],
            testing_rows,
        ),
        "",
        "## Refactoring Results",
        "",
        markdown_table(
            ["Model", "Non-empty", "Differs from input", "Edit similarity", "Code health delta", "Cohesion proxy", "Coupling proxy", "Refactoring quality"],
            refactoring_rows,
        ),
        "",
        "## Interpretation",
        "",
        f"- Best model by test quality score: **{best_testing}**.",
        f"- Best model by refactoring quality score: **{best_refactoring}**.",
        f"- {b1_note}",
        "- Proxy metrics are useful for scalable comparison, but should be complemented by qualitative analysis and real executable coverage on a curated subset.",
        "",
        "## Limitations",
        "",
        "- Coverage proxy is not real JaCoCo coverage.",
        "- Java syntax is not fully parsed.",
        "- Cohesion and coupling are approximations based on generated code text.",
        "- Results should be supplemented with qualitative analysis.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if (root / "metrics" / "testing" / "per_example_metrics.jsonl").exists():
        write_examples("testing", root / "predictions" / "testing", root / "metrics" / "testing" / "per_example_metrics.jsonl", root / "samples" / "testing_examples.md")
    if (root / "metrics" / "refactoring" / "per_example_metrics.jsonl").exists():
        write_examples("refactoring", root / "predictions" / "refactoring", root / "metrics" / "refactoring" / "per_example_metrics.jsonl", root / "samples" / "refactoring_examples.md")
    return report_path
