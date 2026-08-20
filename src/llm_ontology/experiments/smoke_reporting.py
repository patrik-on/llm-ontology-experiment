from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from llm_ontology.experiments.smoke_models import SmokeExperimentConfig, SmokeRunRecord


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
                raise ValueError(f"Invalid smoke run record at {path}:{line_number}: {exc}") from exc
    return records


def latest_run_records(records: Iterable[SmokeRunRecord]) -> dict[str, SmokeRunRecord]:
    latest: dict[str, SmokeRunRecord] = {}
    for record in records:
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
    latest = list(latest_run_records(history).values())
    successes = [record for record in latest if record.status == "success"]
    failures = [record for record in latest if record.status == "failed"]

    summary_rows = _summary_rows(latest)
    summary = {
        "experiment_name": config.experiment_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "default_planned_runs": config.default_planned_runs,
        "planned_runs_current_selection": planned_runs,
        "recorded_run_ids": len(latest),
        "successful_run_ids": len(successes),
        "failed_run_ids": len(failures),
        "history_records": len(history),
        "fairness_passed": bool(fairness_audit.get("passed")),
        "by_task_mode": summary_rows,
    }
    _write_json(output / "summary.json", summary)
    _write_csv(
        output / "summary.csv",
        summary_rows,
        fieldnames=("task", "mode", "success", "failed", "average_primary_score"),
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
            [record for record in history if record.status == "failed"],
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
        rows.append(
            {
                "task": task,
                "mode": mode,
                "success": sum(item.status == "success" for item in items),
                "failed": sum(item.status == "failed" for item in items),
                "average_primary_score": round(mean(scores), 6) if scores else "",
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
        rows.append(
            {
                "run_id": record.run_id,
                "case_id": record.case_id,
                "task": record.task,
                "mode": record.mode.value,
                "selected_collections": trace.get("selected_collections", []),
                "retrieved_documents": len(trace.get("retrieved_documents", [])),
                "prompt_documents": len(trace.get("prompt_document_ids", [])),
                "fusion_strategy": trace.get("fusion_strategy"),
                "rrf_k": trace.get("rrf_k"),
                "candidates_before_deduplication": trace.get(
                    "candidates_before_deduplication", 0
                ),
                "candidates_after_deduplication": trace.get(
                    "candidates_after_deduplication", 0
                ),
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
            "average_prompt_documents": round(
                mean(item["prompt_documents"] for item in items), 6
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
        "generated_test_quality_score"
        if record.task == "testing"
        else "refactoring_quality_score"
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
        f"- Default matrix: {summary['default_planned_runs']} runs",
        f"- Recorded run IDs: {summary['recorded_run_ids']}",
        f"- Successful: {summary['successful_run_ids']}",
        f"- Failed: {summary['failed_run_ids']}",
        f"- Prompt fairness: {'PASS' if summary['fairness_passed'] else 'FAIL'}",
        "",
        "## Case comparison",
        "",
        "| Case | Task | Direct | Single RAG | MultiRAG | Best mode |",
        "|---|---|---:|---:|---:|---|",
    ]
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
