from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_ontology.inference.prompts import build_training_text


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def validate_instruction_record(record: dict[str, Any]) -> None:
    required = {"instruction", "input", "output", "domain"}
    missing = required.difference(record)
    if missing:
        raise ValueError(f"Missing instruction record fields: {', '.join(sorted(missing))}")


def load_instruction_dataset(path: str | Path) -> list[dict[str, Any]]:
    records = read_jsonl(path)
    for record in records:
        validate_instruction_record(record)
    return records


def tokenize_records(records: list[dict[str, str]], tokenizer: Any, max_length: int) -> dict[str, Any]:
    texts = [build_training_text(record) for record in records]
    tokenized = tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors=None,
    )
    tokenized["labels"] = [ids.copy() for ids in tokenized["input_ids"]]
    return tokenized
