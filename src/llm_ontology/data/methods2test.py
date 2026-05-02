from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterator

from llm_ontology.data.format import TESTING_INSTRUCTION, write_jsonl


ASSERTION_MARKERS = (
    "@Test",
    "assert",
    "Assert.",
    "Assertions.",
    "assertEquals",
    "assertTrue",
    "assertFalse",
    "assertNotNull",
    "assertNull",
    "fail(",
)
ALLOWED_CONTEXT_FIELDS = ("src_fm", "src_fm_fc", "src_fm_fc_co", "src_fm_fc_ms", "src_fm_fc_ms_ff")
SOURCE = "methods2test"
SUBSET_SIZES = {"train": 4000, "eval": 500, "test": 500}
SPLIT_OUTPUTS = {"train": "train.jsonl", "eval": "val.jsonl", "test": "test.jsonl"}


@dataclass(frozen=True)
class SplitStats:
    split: str
    loaded: int
    saved: int
    skipped: int
    avg_input_length: float
    avg_output_length: float
    output_path: Path


def corpus_files(raw_dir: str | Path, split: str) -> list[Path]:
    split_dir = Path(raw_dir) / split
    if not split_dir.exists():
        raise FileNotFoundError(f"Missing Methods2Test split directory: {split_dir}")
    return sorted(split_dir.rglob("*_corpus.json"))


def read_corpus_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def is_valid_example(input_text: Any, output_text: Any) -> bool:
    if not isinstance(input_text, str) or not isinstance(output_text, str):
        return False
    input_text = input_text.strip()
    output_text = output_text.strip()
    return (
        bool(input_text)
        and bool(output_text)
        and len(input_text) >= 50
        and len(output_text) >= 50
        and len(input_text) <= 4000
        and len(output_text) <= 6000
        and any(marker in output_text for marker in ASSERTION_MARKERS)
    )


def to_instruction_record(
    input_text: str,
    output_text: str,
    context_field: str,
    source_file: str | Path,
) -> dict[str, str]:
    return {
        "instruction": TESTING_INSTRUCTION,
        "input": input_text.strip(),
        "output": output_text.strip(),
        "domain": "testing",
        "source": SOURCE,
        "context_level": context_field,
        "source_file": Path(source_file).as_posix(),
    }


def iter_split_records(raw_dir: str | Path, split: str, context_field: str) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in corpus_files(raw_dir, split):
        yield path, read_corpus_file(path)


def relative_source_path(path: Path) -> str:
    root = Path.cwd()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def collect_subset(raw_dir: str | Path, split: str, context_field: str, limit: int) -> tuple[int, int, list[dict[str, str]]]:
    loaded = 0
    skipped = 0
    records: list[dict[str, str]] = []

    for path, payload in iter_split_records(raw_dir, split, context_field):
        loaded += 1
        input_text = payload.get(context_field)
        output_text = payload.get("target")
        if not is_valid_example(input_text, output_text):
            skipped += 1
            continue
        records.append(
            to_instruction_record(
                input_text=input_text,
                output_text=output_text,
                context_field=context_field,
                source_file=relative_source_path(path),
            )
        )
        if len(records) >= limit:
            break
    return loaded, skipped, records


def length_stats(records: list[dict[str, str]]) -> tuple[float, float]:
    if not records:
        return 0.0, 0.0
    return mean(len(record["input"]) for record in records), mean(len(record["output"]) for record in records)


def prepare_methods2test(
    raw_dir: str | Path,
    out_dir: str | Path,
    context_field: str = "src_fm",
    subset_sizes: dict[str, int] | None = None,
) -> list[SplitStats]:
    if context_field not in ALLOWED_CONTEXT_FIELDS:
        allowed = ", ".join(ALLOWED_CONTEXT_FIELDS)
        raise ValueError(f"Unsupported context field '{context_field}'. Allowed values: {allowed}")

    sizes = subset_sizes or SUBSET_SIZES
    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    stats: list[SplitStats] = []
    for split in ("train", "eval", "test"):
        loaded, skipped, records = collect_subset(raw_dir, split, context_field, sizes[split])
        output_path = output_root / SPLIT_OUTPUTS[split]
        write_jsonl(records, output_path)
        avg_input, avg_output = length_stats(records)
        stats.append(
            SplitStats(
                split=split,
                loaded=loaded,
                saved=len(records),
                skipped=skipped,
                avg_input_length=avg_input,
                avg_output_length=avg_output,
                output_path=output_path,
            )
        )
    return stats
