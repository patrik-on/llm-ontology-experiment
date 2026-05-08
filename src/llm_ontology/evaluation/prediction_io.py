from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object in {path}:{line_number}")
            records.append(payload)
    return records


def write_jsonl(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(payload: Any, path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, dict):
            for nested_key, nested_value in flatten_record(value).items():
                flat[f"{key}.{nested_key}"] = nested_value
        elif isinstance(value, list):
            flat[key] = json.dumps(value, ensure_ascii=False)
        else:
            flat[key] = value
    return flat


def write_csv(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    rows = [flatten_record(record) for record in records]
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def pick_first(record: dict[str, Any], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return default


def normalize_prediction_record(raw: dict[str, Any], task: str, model_name: str, index: int) -> dict[str, Any]:
    return {
        "id": pick_first(raw, ("id", "sample_id", "refactoring_id"), f"{model_name}:{task}:{index}"),
        "task": task,
        "model_name": model_name,
        "source": raw.get("source", ""),
        "domain": raw.get("domain", task),
        "input": pick_first(raw, ("input", "prompt", "code_before")),
        "expected_output": pick_first(raw, ("expected_output", "output", "code_after", "reference_output")),
        "prediction": pick_first(raw, ("prediction", "generated_output", "output_prediction")),
        "metadata": raw.get("metadata", {}),
        "generation_config": raw.get("generation_config", {}),
    }
