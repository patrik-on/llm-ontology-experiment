from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_EXAMPLE_FIELDS = ("instruction", "input", "output")


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object in {file_path}:{line_number}")
            records.append(payload)
    return records


def validate_example(example: dict) -> bool:
    for field in REQUIRED_EXAMPLE_FIELDS:
        value = example.get(field)
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def _validated(records: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    invalid = [index for index, example in enumerate(records, 1) if not validate_example(example)]
    if invalid:
        first = invalid[0]
        raise ValueError(f"{label} contains {len(invalid)} invalid examples; first invalid row is {first}.")
    return records


def load_instruction_dataset(
    train_file: str | Path,
    val_file: str | Path,
    max_train_samples: int | None = None,
    max_val_samples: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_records = _validated(load_jsonl(train_file), str(train_file))
    val_records = _validated(load_jsonl(val_file), str(val_file))
    if max_train_samples is not None:
        train_records = train_records[:max_train_samples]
    if max_val_samples is not None:
        val_records = val_records[:max_val_samples]
    return train_records, val_records
