from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from llm_ontology.data.format import write_jsonl
from llm_ontology.data.group_split import grouped_split_by_ratios, record_group_key
from llm_ontology.ingestion.manifest import GroupLevel


REFACTORING_TYPES = ("Extract Method", "Rename Method", "Rename Variable", "Remove Parameter")
SOURCE = "marv"


@dataclass(frozen=True)
class MarvStats:
    loaded: int
    saved: int
    skipped: int
    by_type: dict[str, int]
    split_counts: dict[str, int]
    avg_input_length: float
    avg_output_length: float


def load_marv(raw_file: str | Path) -> dict[str, list[dict[str, Any]]]:
    with Path(raw_file).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected MaRV root object in {raw_file}.")
    return payload


def extract_evaluation_votes(evaluations: Any) -> list[int]:
    if not isinstance(evaluations, list):
        return []
    votes: list[int] = []
    for item in evaluations:
        if isinstance(item, int):
            votes.append(item)
        elif isinstance(item, dict):
            for key in ("vote", "votes", "evaluation", "label", "value"):
                value = item.get(key)
                if isinstance(value, int):
                    votes.append(value)
                    break
    return votes


def is_valid_record(record: dict[str, Any], max_input_chars: int, max_output_chars: int) -> bool:
    input_text = record.get("code_before")
    output_text = record.get("code_after")
    if not isinstance(input_text, str) or not isinstance(output_text, str):
        return False
    input_text = input_text.strip()
    output_text = output_text.strip()
    return (
        bool(input_text)
        and bool(output_text)
        and len(input_text) >= 50
        and len(output_text) >= 50
        and len(input_text) <= max_input_chars
        and len(output_text) <= max_output_chars
    )


def to_instruction_record(record: dict[str, Any], refactoring_type: str) -> dict[str, Any]:
    commit_link = str(record.get("commit_link", ""))
    return {
        "instruction": (
            "Vygeneruj refaktorovanú verziu nasledujúceho Java kódu podľa typu refaktoringu: "
            f"{refactoring_type}."
        ),
        "input": str(record.get("code_before", "")).strip(),
        "output": str(record.get("code_after", "")).strip(),
        "domain": "refactoring",
        "source": SOURCE,
        "refactoring_type": refactoring_type,
        "refactoring_id": str(record.get("refactoring_id", "")),
        "commit_sha": str(record.get("commit_sha", "")),
        "commit_link": commit_link,
        "repository": commit_link.partition("/commit/")[0],
        "file_path": str(record.get("file_path", "")),
        "description": str(record.get("description", "")),
        "evaluation_votes": extract_evaluation_votes(record.get("evaluations")),
    }


def build_instruction_records(
    data: dict[str, list[dict[str, Any]]],
    max_input_chars: int = 12000,
    max_output_chars: int = 12000,
) -> tuple[int, int, list[dict[str, Any]]]:
    loaded = 0
    skipped = 0
    records: list[dict[str, Any]] = []
    for refactoring_type, items in data.items():
        if refactoring_type not in REFACTORING_TYPES:
            continue
        for item in items:
            loaded += 1
            if not is_valid_record(item, max_input_chars, max_output_chars):
                skipped += 1
                continue
            records.append(to_instruction_record(item, refactoring_type))
    return loaded, skipped, records


def stratified_split(
    records: list[dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    if round(train_ratio + val_ratio + test_ratio, 8) != 1.0:
        raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.0")

    return grouped_split_by_ratios(
        records,
        ratios={"train": train_ratio, "val": val_ratio, "test": test_ratio},
        group_key=lambda record: record_group_key(record, GroupLevel.COMMIT),
        seed=seed,
    )


def count_by_type(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(record["refactoring_type"] for record in records))


def average_lengths(records: list[dict[str, Any]]) -> tuple[float, float]:
    if not records:
        return 0.0, 0.0
    return mean(len(record["input"]) for record in records), mean(len(record["output"]) for record in records)


def prepare_marv(
    raw_file: str | Path,
    out_dir: str | Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    max_input_chars: int = 12000,
    max_output_chars: int = 12000,
) -> MarvStats:
    data = load_marv(raw_file)
    loaded, skipped, records = build_instruction_records(data, max_input_chars, max_output_chars)
    splits = stratified_split(records, train_ratio, val_ratio, test_ratio, seed)

    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    for split, split_records in splits.items():
        write_jsonl(split_records, output_root / f"{split}.jsonl")

    avg_input, avg_output = average_lengths(records)
    return MarvStats(
        loaded=loaded,
        saved=len(records),
        skipped=skipped,
        by_type=count_by_type(records),
        split_counts={split: len(split_records) for split, split_records in splits.items()},
        avg_input_length=avg_input,
        avg_output_length=avg_output,
    )
