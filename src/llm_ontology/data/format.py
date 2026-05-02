from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from llm_ontology.data.clean import clean_record, is_non_empty_pair


REFACTORING_INSTRUCTION = "Refaktoruj nasledujúcu Java metódu."
TESTING_INSTRUCTION = "Vygeneruj JUnit test pre nasledujúcu Java metódu."

FIELD_CANDIDATES = {
    "refactoring": {
        "input": ("input", "source", "original", "before", "before_code", "code", "method"),
        "output": ("output", "target", "refactored", "after", "after_code", "refactored_code"),
    },
    "testing": {
        "input": ("input", "focal_method", "method", "source", "code"),
        "output": ("output", "test", "test_code", "unit_test", "junit_test"),
    },
}


def pick_field(record: dict[str, Any], candidates: Iterable[str]) -> str:
    for key in candidates:
        if key in record and str(record[key]).strip():
            return str(record[key])
    return ""


def to_instruction_record(record: dict[str, Any], domain: str) -> dict[str, str] | None:
    cleaned = clean_record(record)
    mapping = FIELD_CANDIDATES[domain]
    input_text = pick_field(cleaned, mapping["input"])
    output_text = pick_field(cleaned, mapping["output"])
    if not is_non_empty_pair(input_text, output_text):
        return None
    return {
        "instruction": REFACTORING_INSTRUCTION if domain == "refactoring" else TESTING_INSTRUCTION,
        "input": input_text,
        "output": output_text,
        "domain": domain,
    }


def read_records(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".jsonl":
        with file_path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if file_path.suffix.lower() == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list):
                    return value
            return [payload]
    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError(f"Unsupported data file format: {file_path}")


def load_domain_records(files: Iterable[str | Path], domain: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in files:
        for raw_record in read_records(path):
            formatted = to_instruction_record(raw_record, domain)
            if formatted:
                records.append(formatted)
    return records


def write_jsonl(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
