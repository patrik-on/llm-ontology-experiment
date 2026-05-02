from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from llm_ontology.core.paths import ensure_dir, resolve_path
from llm_ontology.evaluation.metrics import aggregate_scores, load_predictions
from llm_ontology.evaluation.refactoring import evaluate_refactoring
from llm_ontology.evaluation.testing import evaluate_testing


def evaluate_predictions(config: dict) -> tuple[Path, Path]:
    result_dir = ensure_dir(resolve_path(config["output"]["result_dir"]))
    predictions_path = result_dir / "predictions.jsonl"
    records = load_predictions(predictions_path)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_domain[record.get("domain", "unknown")].append(record)

    metrics: dict[str, object] = {"overall": aggregate_scores(records), "domains": {}}
    if "refactoring" in by_domain:
        metrics["domains"]["refactoring"] = evaluate_refactoring(by_domain["refactoring"])
    if "testing" in by_domain:
        metrics["domains"]["testing"] = evaluate_testing(by_domain["testing"])

    metrics_path = result_dir / "metrics.json"
    report_path = result_dir / "report.md"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(render_report(config, metrics), encoding="utf-8")
    return metrics_path, report_path


def render_report(config: dict, metrics: dict) -> str:
    lines = [
        f"# Experiment Report: {config['experiment']['name']}",
        "",
        f"- Domain: {config['experiment']['domain']}",
        f"- Method: {config['experiment']['method']}",
        f"- Count: {metrics['overall']['count']}",
        f"- Exact match: {metrics['overall']['exact_match']:.4f}",
        f"- Token F1: {metrics['overall']['token_f1']:.4f}",
    ]
    return "\n".join(lines) + "\n"
