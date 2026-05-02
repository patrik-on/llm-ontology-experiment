from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.format import write_jsonl


SPLITS = ("train", "val", "test")
REFACTORING_EXPECTED = {"train": 4478, "val": 600, "test": 608}
COMBINED_EXPECTED = {"train": 8000, "val": 1000, "test": 1000}
COMBINED_TAKE = {
    "train": {"testing": 4000, "refactoring_ml4ref": 4000},
    "val": {"testing": 500, "refactoring_ml4ref": 500},
    "test": {"testing": 500, "refactoring_ml4ref": 500},
}


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


def shuffled(records: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    output = list(records)
    random.Random(seed).shuffle(output)
    return output


def take_records(records: list[dict[str, Any]], count: int, label: str) -> list[dict[str, Any]]:
    if len(records) < count:
        raise ValueError(f"Need {count} records from {label}, found only {len(records)}.")
    return records[:count]


def require_domain(records: list[dict[str, Any]], domain: str, label: str) -> None:
    bad = sum(1 for record in records if record.get("domain") != domain)
    if bad:
        raise ValueError(f"{label} has {bad} records where domain is not {domain!r}.")


def require_source(records: list[dict[str, Any]], sources: set[str], label: str) -> None:
    bad_sources = sorted({str(record.get("source")) for record in records if record.get("source") not in sources})
    if bad_sources:
        raise ValueError(f"{label} has unsupported source values: {bad_sources}")


def validate_count(records: list[dict[str, Any]], expected: int, label: str) -> None:
    if len(records) != expected:
        raise ValueError(f"{label} expected {expected} records, got {len(records)}.")


def split_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    input_lengths = [len(str(record.get("input", ""))) for record in records]
    output_lengths = [len(str(record.get("output", ""))) for record in records]
    return {
        "count": len(records),
        "domains": dict(Counter(str(record.get("domain")) for record in records)),
        "sources": dict(Counter(str(record.get("source")) for record in records)),
        "avg_input_length": mean(input_lengths) if input_lengths else 0.0,
        "avg_output_length": mean(output_lengths) if output_lengths else 0.0,
    }


def prepare_refactoring_dataset(
    refactoring_ml4ref_dir: Path,
    refactoring_marv_dir: Path,
    out_dir: Path,
    seed: int,
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    out_dir.mkdir(parents=True, exist_ok=True)

    for split in SPLITS:
        ml4ref = read_jsonl(refactoring_ml4ref_dir / f"{split}.jsonl")
        marv = read_jsonl(refactoring_marv_dir / f"{split}.jsonl")
        require_domain(ml4ref, "refactoring", f"ml4refactoring/{split}")
        require_domain(marv, "refactoring", f"marv/{split}")
        require_source(ml4ref, {"ml4refactoring"}, f"ml4refactoring/{split}")
        require_source(marv, {"marv"}, f"marv/{split}")

        records = shuffled(ml4ref + marv, seed)
        validate_count(records, REFACTORING_EXPECTED[split], f"refactoring/{split}")
        write_jsonl(records, out_dir / f"{split}.jsonl")
        stats[split] = split_stats(records)

    return stats


def prepare_combined_dataset(
    testing_dir: Path,
    refactoring_ml4ref_dir: Path,
    out_dir: Path,
    seed: int,
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    out_dir.mkdir(parents=True, exist_ok=True)

    for split in SPLITS:
        testing = shuffled(read_jsonl(testing_dir / f"{split}.jsonl"), seed)
        ml4ref = shuffled(read_jsonl(refactoring_ml4ref_dir / f"{split}.jsonl"), seed)
        require_domain(testing, "testing", f"testing/{split}")
        require_domain(ml4ref, "refactoring", f"ml4refactoring/{split}")
        require_source(testing, {"methods2test"}, f"testing/{split}")
        require_source(ml4ref, {"ml4refactoring"}, f"ml4refactoring/{split}")

        records = shuffled(
            take_records(testing, COMBINED_TAKE[split]["testing"], f"testing/{split}")
            + take_records(ml4ref, COMBINED_TAKE[split]["refactoring_ml4ref"], f"ml4refactoring/{split}"),
            seed,
        )
        validate_count(records, COMBINED_EXPECTED[split], f"combined/{split}")
        write_jsonl(records, out_dir / f"{split}.jsonl")
        stats[split] = split_stats(records)

    return stats


def print_stats(title: str, stats: dict[str, dict[str, Any]]) -> None:
    print(f"\n{title}")
    for split in SPLITS:
        split_info = stats[split]
        print(f"- {split}: {split_info['count']}")
        print(f"  domains: {split_info['domains']}")
        print(f"  sources: {split_info['sources']}")
        print(f"  avg_input_length: {split_info['avg_input_length']:.2f}")
        print(f"  avg_output_length: {split_info['avg_output_length']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare final B2-R and B1 JSONL datasets.")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    refactoring_stats = prepare_refactoring_dataset(
        refactoring_ml4ref_dir=processed_dir / "refactoring_ml4ref",
        refactoring_marv_dir=processed_dir / "refactoring_marv",
        out_dir=processed_dir / "refactoring",
        seed=args.seed,
    )
    combined_stats = prepare_combined_dataset(
        testing_dir=processed_dir / "testing",
        refactoring_ml4ref_dir=processed_dir / "refactoring_ml4ref",
        out_dir=processed_dir / "combined",
        seed=args.seed,
    )

    print_stats("Final B2-R refactoring dataset", refactoring_stats)
    print_stats("Final B1 combined dataset", combined_stats)


if __name__ == "__main__":
    main()
