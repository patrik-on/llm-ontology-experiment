from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from llm_ontology.data.format import write_jsonl


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
        "commit_link": str(record.get("commit_link", "")),
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

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_type[record["refactoring_type"]].append(record)

    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}
    for group in by_type.values():
        shuffled = list(group)
        rng.shuffle(shuffled)
        total = len(shuffled)
        train_count = int(total * train_ratio)
        val_count = int(total * val_ratio)
        if total >= 3:
            train_count = max(1, train_count)
            val_count = max(1, val_count)
        test_count = total - train_count - val_count
        if total >= 3 and test_count == 0:
            test_count = 1
            if train_count >= val_count and train_count > 1:
                train_count -= 1
            elif val_count > 1:
                val_count -= 1
        splits["train"].extend(shuffled[:train_count])
        splits["val"].extend(shuffled[train_count : train_count + val_count])
        splits["test"].extend(shuffled[train_count + val_count : train_count + val_count + test_count])

    for split_records in splits.values():
        rng.shuffle(split_records)
    return splits


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
