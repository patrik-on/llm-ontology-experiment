from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from llm_ontology.evaluation.metrics_runner import (
    aggregate_refactoring,
    aggregate_testing,
)
from llm_ontology.experiments.smoke_models import SmokeExperimentConfig, SmokeRunRecord


SUMMARY_FIELDS = (
    "task",
    "mode",
    "success",
    "failed",
    "average_primary_score",
    "count",
    "output_non_empty_rate",
    "contains_test_annotation_rate",
    "has_assertion_rate",
    "target_method_invocation_rate",
    "trivial_test_smell_rate",
    "avg_test_quality_score",
    "median_test_quality_score",
    "min_test_quality_score",
    "max_test_quality_score",
    "avg_coverage_proxy_score",
    "output_differs_from_input_rate",
    "avg_edit_similarity",
    "avg_code_health_delta_score",
    "avg_cohesion_proxy_score",
    "avg_coupling_proxy_score",
    "avg_refactoring_quality_score",
    "median_refactoring_quality_score",
    "min_refactoring_quality_score",
    "max_refactoring_quality_score",
    "avg_complexity_delta",
    "avg_loc_delta",
)


def append_run_record(path: Path, record: SmokeRunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
        handle.flush()


def read_run_history(path: Path) -> list[SmokeRunRecord]:
    if not path.is_file():
        return []
    records: list[SmokeRunRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(SmokeRunRecord.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid smoke run record at {path}:{line_number}: {exc}"
                ) from exc
    return records


def latest_run_records(
    records: Iterable[SmokeRunRecord],
    *,
    baseline_id: str | None = None,
    baseline_fingerprint: str | None = None,
) -> dict[str, SmokeRunRecord]:
    latest: dict[str, SmokeRunRecord] = {}
    for record in records:
        if baseline_id is not None and record.baseline_id != baseline_id:
            continue
        if baseline_fingerprint is not None and record.baseline_fingerprint != baseline_fingerprint:
            continue
        previous = latest.get(record.run_id)
        if previous is None or record.attempt >= previous.attempt:
            latest[record.run_id] = record
    return latest


def write_smoke_reports(
    config: SmokeExperimentConfig,
    *,
    planned_runs: int,
    fairness_audit: dict[str, Any],
) -> None:
    output = config.output_dir
    output.mkdir(parents=True, exist_ok=True)
    runs_path = output / "runs.jsonl"
    runs_path.touch(exist_ok=True)
    history = read_run_history(runs_path)
    baseline_history = [
        record
        for record in history
        if record.baseline_id == config.baseline_id
        and record.baseline_fingerprint == config.baseline_fingerprint
    ]
    latest = list(
        latest_run_records(
            baseline_history,
            baseline_id=config.baseline_id,
            baseline_fingerprint=config.baseline_fingerprint,
        ).values()
    )
    successes = [record for record in latest if record.status == "success"]
    failures = [record for record in latest if record.status == "failed"]

    summary_rows = _summary_rows(latest)
    summary = {
        "experiment_name": config.experiment_name,
        "baseline_id": config.baseline_id,
        "baseline_fingerprint": config.baseline_fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "default_planned_runs": config.default_planned_runs,
        "planned_runs_current_selection": planned_runs,
        "recorded_run_ids": len(latest),
        "successful_run_ids": len(successes),
        "failed_run_ids": len(failures),
        "history_records": len(baseline_history),
        "raw_history_records": len(history),
        "excluded_history_records": len(history) - len(baseline_history),
        "fairness_passed": bool(fairness_audit.get("passed")),
        "evaluation_metric_contract": "canonical_finetuning_eval_metrics",
        "by_task_mode": summary_rows,
    }
    _write_json(output / "summary.json", summary)
    _write_csv(
        output / "summary.csv",
        summary_rows,
        fieldnames=SUMMARY_FIELDS,
    )

    comparisons = _case_comparisons(latest)
    _write_json(output / "case_comparison.json", comparisons)
    _write_csv(
        output / "case_comparison.csv",
        comparisons,
        fieldnames=(
            "case_id",
            "task",
            "difficulty",
            "no_rag_status",
            "no_rag_score",
            "single_collection_rag_status",
            "single_collection_rag_score",
            "multi_collection_rag_status",
            "multi_collection_rag_score",
            "best_mode",
        ),
    )
    _write_json(output / "retrieval_analysis.json", _retrieval_analysis(successes))
    _write_json(
        output / "failure_analysis.json",
        _failure_analysis(
            failures,
            [record for record in baseline_history if record.status == "failed"],
        ),
    )
    _write_json(output / "fairness_audit.json", fairness_audit)
    _write_text(output / "report.md", _markdown_report(summary, comparisons, failures))


def _summary_rows(records: list[SmokeRunRecord]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[SmokeRunRecord]] = defaultdict(list)
    for record in records:
        groups[(record.task, record.mode.value)].append(record)
    rows = []
    for (task, mode), items in sorted(groups.items()):
        scores = [score for item in items if (score := _primary_score(item)) is not None]
        successful_metrics = [item.metrics for item in items if item.status == "success"]
        evaluation_aggregates = (
            aggregate_testing(successful_metrics)
            if task == "testing"
            else aggregate_refactoring(successful_metrics)
        )
        rows.append(
            {
                "task": task,
                "mode": mode,
                "success": sum(item.status == "success" for item in items),
                "failed": sum(item.status == "failed" for item in items),
                "average_primary_score": round(mean(scores), 6) if scores else "",
                **evaluation_aggregates,
            }
        )
    return rows


def _case_comparisons(records: list[SmokeRunRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[SmokeRunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.case_id].append(record)
    rows: list[dict[str, Any]] = []
    for case_id, items in sorted(grouped.items()):
        first = items[0]
        by_mode = {item.mode.value: item for item in items}
        scores = {
            mode: score
            for mode, item in by_mode.items()
            if (score := _primary_score(item)) is not None
        }
        best_mode = max(scores, key=scores.get) if scores else ""
        row: dict[str, Any] = {
            "case_id": case_id,
            "task": first.task,
            "difficulty": first.difficulty,
            "best_mode": best_mode,
        }
        for mode in (
            "no_rag",
            "single_collection_rag",
            "multi_collection_rag",
        ):
            item = by_mode.get(mode)
            row[f"{mode}_status"] = item.status if item else "not_run"
            score = _primary_score(item) if item else None
            row[f"{mode}_score"] = "" if score is None else score
        rows.append(row)
    return rows


def _retrieval_analysis(records: list[SmokeRunRecord]) -> dict[str, Any]:
    rows = []
    for record in records:
        experiment = record.experiment_record or {}
        trace = experiment.get("retrieval_trace") or {}
        token_budget = experiment.get("token_budget") or {}
        rows.append(
            {
                "run_id": record.run_id,
                "case_id": record.case_id,
                "task": record.task,
                "mode": record.mode.value,
                "selected_collections": trace.get("selected_collections", []),
                "applied_filters": trace.get("applied_filters", {}),
                "retrieved_documents": len(trace.get("retrieved_documents", [])),
                "prompt_documents": len(trace.get("prompt_document_ids", [])),
                "retrieval_tokens": token_budget.get("retrieval_tokens", 0),
                "max_document_tokens": token_budget.get("max_document_tokens"),
                "truncated_documents": len(token_budget.get("truncated_document_ids", [])),
                "final_prompt_tokens": token_budget.get("final_prompt_tokens"),
                "runtime_prompt_eval_count": token_budget.get("runtime_prompt_eval_count"),
                "runtime_prompt_truncation_suspected": token_budget.get(
                    "runtime_prompt_truncation_suspected"
                ),
                "fusion_strategy": trace.get("fusion_strategy"),
                "rrf_k": trace.get("rrf_k"),
                "candidates_before_deduplication": trace.get("candidates_before_deduplication", 0),
                "candidates_after_deduplication": trace.get("candidates_after_deduplication", 0),
                "retrieval_latency_ms": trace.get("total_latency_ms", 0.0),
            }
        )
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in sorted({row["mode"] for row in rows}):
        items = [row for row in rows if row["mode"] == mode]
        by_mode[mode] = {
            "runs": len(items),
            "average_retrieved_documents": round(
                mean(item["retrieved_documents"] for item in items), 6
            ),
            "average_prompt_documents": round(mean(item["prompt_documents"] for item in items), 6),
            "average_retrieval_tokens": round(
                mean(float(item["retrieval_tokens"]) for item in items), 6
            ),
            "average_truncated_documents": round(
                mean(item["truncated_documents"] for item in items), 6
            ),
            "runtime_prompt_truncation_suspected_count": sum(
                item["runtime_prompt_truncation_suspected"] is True for item in items
            ),
            "average_retrieval_latency_ms": round(
                mean(float(item["retrieval_latency_ms"]) for item in items), 6
            ),
        }
    return {"by_mode": by_mode, "runs": rows}


def _failure_analysis(
    failures: list[SmokeRunRecord],
    historical_failures: list[SmokeRunRecord],
) -> dict[str, Any]:
    return {
        "failure_count": len(failures),
        "historical_failure_attempt_count": len(historical_failures),
        "by_error_type": dict(
            Counter(item.error_type or "unknown" for item in historical_failures)
        ),
        "failures": [
            {
                "run_id": item.run_id,
                "case_id": item.case_id,
                "task": item.task,
                "mode": item.mode.value,
                "attempt": item.attempt,
                "error_type": item.error_type,
                "error_message": item.error_message,
            }
            for item in historical_failures
        ],
    }


def _primary_score(record: SmokeRunRecord | None) -> float | None:
    if record is None or record.status != "success":
        return None
    key = (
        "generated_test_quality_score" if record.task == "testing" else "refactoring_quality_score"
    )
    value = record.metrics.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _markdown_report(
    summary: dict[str, Any],
    comparisons: list[dict[str, Any]],
    failures: list[SmokeRunRecord],
) -> str:
    lines = [
        "# Smoke experiment report",
        "",
        f"- Experiment: `{summary['experiment_name']}`",
        f"- Baseline fingerprint: `{summary['baseline_fingerprint']}`",
        f"- Default matrix: {summary['default_planned_runs']} runs",
        f"- Recorded run IDs: {summary['recorded_run_ids']}",
        f"- Successful: {summary['successful_run_ids']}",
        f"- Failed: {summary['failed_run_ids']}",
        f"- Prompt fairness: {'PASS' if summary['fairness_passed'] else 'FAIL'}",
        "- Metrics: canonical fine-tuning evaluation aggregates",
        "",
        "## Evaluation metrics",
        "",
        "### Testing",
        "",
        "| Mode | Test quality | Coverage proxy | @Test rate | Assertion rate | "
        "Target invocation | Trivial smell |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["by_task_mode"]:
        if row["task"] != "testing":
            continue
        lines.append(
            "| {mode} | {quality} | {coverage} | {annotation} | {assertion} | "
            "{target} | {smell} |".format(
                mode=row["mode"],
                quality=_format_metric(row.get("avg_test_quality_score")),
                coverage=_format_metric(row.get("avg_coverage_proxy_score")),
                annotation=_format_metric(row.get("contains_test_annotation_rate")),
                assertion=_format_metric(row.get("has_assertion_rate")),
                target=_format_metric(row.get("target_method_invocation_rate")),
                smell=_format_metric(row.get("trivial_test_smell_rate")),
            )
        )
    lines.extend(
        [
            "",
            "### Refactoring",
            "",
            "| Mode | Quality | Code health | Cohesion | Coupling | Complexity Δ | LOC Δ |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["by_task_mode"]:
        if row["task"] != "refactoring":
            continue
        lines.append(
            "| {mode} | {quality} | {health} | {cohesion} | {coupling} | "
            "{complexity} | {loc} |".format(
                mode=row["mode"],
                quality=_format_metric(row.get("avg_refactoring_quality_score")),
                health=_format_metric(row.get("avg_code_health_delta_score")),
                cohesion=_format_metric(row.get("avg_cohesion_proxy_score")),
                coupling=_format_metric(row.get("avg_coupling_proxy_score")),
                complexity=_format_metric(row.get("avg_complexity_delta")),
                loc=_format_metric(row.get("avg_loc_delta")),
            )
        )
    lines.extend(
        [
            "",
            "## Case comparison",
            "",
            "| Case | Task | Direct | Single RAG | MultiRAG | Best mode |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in comparisons:
        lines.append(
            "| {case_id} | {task} | {no_rag_score} | {single_collection_rag_score} | "
            "{multi_collection_rag_score} | {best_mode} |".format(**row)
        )
    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(
            f"- `{item.run_id}`: {item.error_type}: {item.error_message}" for item in failures
        )
    else:
        lines.append("No latest run is marked as failed.")
    return "\n".join(lines) + "\n"


def _format_metric(value: Any) -> str:
    return f"{float(value):.4f}" if isinstance(value, (int, float)) else ""


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    fieldnames: tuple[str, ...],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    _write_text(path, buffer.getvalue())


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
