from __future__ import annotations

import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from llm_ontology.data.group_split import grouped_split_by_sizes, record_group_key
from llm_ontology.ingestion.manifest import GroupLevel

from llm_ontology.data.format import write_jsonl


SOURCE = "ml4refactoring"
DEFAULT_DATASET_DIR = Path("C:/datasets/ml4refactoring/all/dataset")
DEFAULT_TEMP_DIR = Path("C:/datasets/ml4refactoring/tmp")
DEFAULT_OUT_DIR = Path("data/processed/refactoring_ml4ref")
SUPPORTED_REFACTORING_TYPES = (
    "Extract Method",
    "Move Method",
    "Pull Up Method",
    "Push Down Method",
    "Inline Method",
    "Rename Method",
    "Move Attribute",
    "Pull Up Attribute",
    "Push Down Attribute",
    "Rename Attribute",
    "Extract Class",
    "Move Class",
    "Rename Class",
    "Extract Interface",
    "Extract Superclass",
    "Remove Parameter",
    "Add Parameter",
    "Rename Variable",
)


@dataclass(frozen=True)
class ML4RefactoringStats:
    processed_project_zips: int
    skipped_projects: int
    commits: int
    candidate_pairs: int
    saved: int
    skipped_examples: int
    by_type: dict[str, int]
    split_counts: dict[str, int]
    avg_input_length: float
    avg_output_length: float
    output_dir: Path


@dataclass(frozen=True)
class ProjectCollectionResult:
    records: list[dict[str, Any]]
    project_name: str | None
    commits: int
    candidate_pairs: int
    skipped_examples: int


@dataclass(frozen=True)
class ML4RefactoringInspection:
    dataset_dir: Path
    project_zip_count: int
    first_project_zips: list[tuple[Path, int]]
    inspected_zip: Path | None
    project_name: str | None
    commit_count: int
    before_after_commit_count: int
    candidate_file_count: int
    sample_files: list[str]
    sample_refactoring_types: list[tuple[str, str]]


def extract_refactoring_type(file_name: str) -> str:
    for refactoring_type in SUPPORTED_REFACTORING_TYPES:
        if refactoring_type in file_name:
            return refactoring_type
    return "unknown"


def is_candidate_code_file(path: Path) -> bool:
    return path.is_file() and ".java" in path.name and "-astc" not in path.name and path.stat().st_size > 0


def is_valid_pair(
    before_text: str,
    after_text: str,
    max_input_chars: int,
    max_output_chars: int,
) -> bool:
    before_text = before_text.strip()
    after_text = after_text.strip()
    return (
        bool(before_text)
        and bool(after_text)
        and len(before_text) >= 50
        and len(after_text) >= 50
        and len(before_text) <= max_input_chars
        and len(after_text) <= max_output_chars
        and before_text != after_text
    )


def find_project_storage_dir(extracted_project_dir: Path) -> Path | None:
    output_dir = extracted_project_dir / "output"
    if not output_dir.exists():
        return None
    storage_dirs = sorted(path for path in output_dir.glob("*/storage") if path.is_dir())
    if not storage_dirs:
        return None
    return storage_dirs[0]


def project_name_from_storage(storage_dir: Path) -> str:
    return storage_dir.parent.name


def read_text_lossy(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def instruction_for(refactoring_type: str) -> str:
    return (
        "Vygeneruj refaktorovanú verziu nasledujúceho Java kódu podľa typu refaktoringu: "
        f"{refactoring_type}."
    )


def collect_pairs_from_commit(commit_dir: Path, project_name: str) -> list[dict[str, Any]]:
    before_dir = commit_dir / "before-refactoring"
    after_dir = commit_dir / "after-refactoring"
    if not before_dir.is_dir() or not after_dir.is_dir():
        return []

    before_files = {path.relative_to(before_dir).as_posix(): path for path in before_dir.rglob("*") if is_candidate_code_file(path)}
    after_files = {path.relative_to(after_dir).as_posix(): path for path in after_dir.rglob("*") if is_candidate_code_file(path)}
    records: list[dict[str, Any]] = []

    for relative_path in sorted(before_files.keys() & after_files.keys()):
        before_text = read_text_lossy(before_files[relative_path])
        after_text = read_text_lossy(after_files[relative_path])
        refactoring_type = extract_refactoring_type(Path(relative_path).name)
        records.append(
            {
                "instruction": instruction_for(refactoring_type),
                "input": before_text,
                "output": after_text,
                "domain": "refactoring",
                "source": SOURCE,
                "project": project_name,
                "commit_sha": commit_dir.name,
                "file_path": relative_path,
                "refactoring_type": refactoring_type,
            }
        )
    return records


def count_candidate_pairs(commit_dir: Path) -> int:
    before_dir = commit_dir / "before-refactoring"
    after_dir = commit_dir / "after-refactoring"
    if not before_dir.is_dir() or not after_dir.is_dir():
        return 0
    before_paths = {path.relative_to(before_dir).as_posix() for path in before_dir.rglob("*") if is_candidate_code_file(path)}
    after_paths = {path.relative_to(after_dir).as_posix() for path in after_dir.rglob("*") if is_candidate_code_file(path)}
    return len(before_paths & after_paths)


def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            destination = (target_dir / member.filename).resolve()
            if target_root != destination and target_root not in destination.parents:
                raise ValueError(f"Refusing to extract path outside target directory: {member.filename}")
        archive.extractall(target_dir)


def clean_project_temp_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def collect_pairs_from_extracted_project(
    extracted_project_dir: Path,
    max_examples: int | None = None,
    max_input_chars: int = 12000,
    max_output_chars: int = 12000,
) -> ProjectCollectionResult:
    storage_dir = find_project_storage_dir(extracted_project_dir)
    if storage_dir is None:
        return ProjectCollectionResult([], None, 0, 0, 0)

    project_name = project_name_from_storage(storage_dir)
    records: list[dict[str, Any]] = []
    commits = 0
    candidate_pairs = 0
    skipped_examples = 0

    for commit_dir in sorted(path for path in storage_dir.iterdir() if path.is_dir()):
        commits += 1
        candidate_pairs += count_candidate_pairs(commit_dir)
        for record in collect_pairs_from_commit(commit_dir, project_name):
            if is_valid_pair(record["input"], record["output"], max_input_chars, max_output_chars):
                records.append(record)
                if max_examples is not None and len(records) >= max_examples:
                    return ProjectCollectionResult(records, project_name, commits, candidate_pairs, skipped_examples)
            else:
                skipped_examples += 1

    return ProjectCollectionResult(records, project_name, commits, candidate_pairs, skipped_examples)


def collect_pairs_from_project_zip(
    project_zip: Path,
    temp_dir: Path,
    max_examples: int | None = None,
) -> list[dict[str, Any]]:
    result = collect_project_zip(project_zip, temp_dir, max_examples=max_examples)
    return result.records


def collect_project_zip(
    project_zip: Path,
    temp_dir: Path,
    max_examples: int | None = None,
    max_input_chars: int = 12000,
    max_output_chars: int = 12000,
) -> ProjectCollectionResult:
    project_temp_dir = temp_dir / project_zip.stem
    clean_project_temp_dir(project_temp_dir)
    try:
        safe_extract_zip(project_zip, project_temp_dir)
        return collect_pairs_from_extracted_project(
            project_temp_dir,
            max_examples=max_examples,
            max_input_chars=max_input_chars,
            max_output_chars=max_output_chars,
        )
    finally:
        clean_project_temp_dir(project_temp_dir)


def project_zip_files(dataset_dir: str | Path, max_projects: int | None = None) -> list[Path]:
    zips = sorted(Path(dataset_dir).glob("*.zip"))
    if max_projects is not None:
        return zips[:max_projects]
    return zips


def average_lengths(records: list[dict[str, Any]]) -> tuple[float, float]:
    if not records:
        return 0.0, 0.0
    return mean(len(record["input"]) for record in records), mean(len(record["output"]) for record in records)


def split_records(
    records: list[dict[str, Any]],
    train_size: int,
    val_size: int,
    test_size: int,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    required = train_size + val_size + test_size
    if len(records) < required:
        raise ValueError(f"Need {required} valid records, collected only {len(records)}.")
    return grouped_split_by_sizes(
        records,
        sizes={"train": train_size, "val": val_size, "test": test_size},
        group_key=lambda record: record_group_key(record, GroupLevel.PROJECT),
        seed=seed,
    )


def prepare_ml4refactoring_dataset(
    dataset_dir: str | Path,
    output_dir: str | Path,
    temp_dir: str | Path = DEFAULT_TEMP_DIR,
    train_size: int = 4000,
    val_size: int = 500,
    test_size: int = 500,
    seed: int = 42,
    max_input_chars: int = 12000,
    max_output_chars: int = 12000,
    max_projects: int | None = None,
    max_total: int | None = None,
    max_train: int | None = None,
    max_val: int | None = None,
    max_test: int | None = None,
    progress: bool = False,
) -> ML4RefactoringStats:
    if max_train is not None:
        train_size = max_train
    if max_val is not None:
        val_size = max_val
    if max_test is not None:
        test_size = max_test

    target_total = max_total or train_size + val_size + test_size
    records: list[dict[str, Any]] = []
    processed_project_zips = 0
    skipped_projects = 0
    commits = 0
    candidate_pairs = 0
    skipped_examples = 0

    temp_root = Path(temp_dir)
    temp_root.mkdir(parents=True, exist_ok=True)

    for project_zip in project_zip_files(dataset_dir, max_projects=max_projects):
        remaining = target_total - len(records)
        if remaining <= 0:
            break
        processed_project_zips += 1
        result = collect_project_zip(
            project_zip=project_zip,
            temp_dir=temp_root,
            max_examples=remaining,
            max_input_chars=max_input_chars,
            max_output_chars=max_output_chars,
        )
        if result.project_name is None:
            skipped_projects += 1
        commits += result.commits
        candidate_pairs += result.candidate_pairs
        skipped_examples += result.skipped_examples
        records.extend(result.records)
        if progress:
            print(
                f"[{processed_project_zips}] {project_zip.name}: "
                f"+{len(result.records)} valid, total={len(records)}/{target_total}"
            )

    splits = split_records(records, train_size, val_size, test_size, seed)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    for split, split_records_ in splits.items():
        write_jsonl(split_records_, output_root / f"{split}.jsonl")

    final_records = splits["train"] + splits["val"] + splits["test"]
    avg_input, avg_output = average_lengths(final_records)
    return ML4RefactoringStats(
        processed_project_zips=processed_project_zips,
        skipped_projects=skipped_projects,
        commits=commits,
        candidate_pairs=candidate_pairs,
        saved=len(final_records),
        skipped_examples=skipped_examples + max(0, len(records) - len(final_records)),
        by_type=dict(Counter(record["refactoring_type"] for record in final_records)),
        split_counts={split: len(split_records_) for split, split_records_ in splits.items()},
        avg_input_length=avg_input,
        avg_output_length=avg_output,
        output_dir=output_root,
    )


def inspect_ml4refactoring(
    dataset_dir: str | Path = DEFAULT_DATASET_DIR,
    project_zip: str | Path | None = None,
    max_projects: int | None = None,
    temp_dir: str | Path = DEFAULT_TEMP_DIR,
) -> ML4RefactoringInspection:
    dataset_path = Path(dataset_dir)
    zips = project_zip_files(dataset_path, max_projects=max_projects)
    first_zips = [(path, path.stat().st_size) for path in zips[:20]]
    inspected_zip = Path(project_zip) if project_zip is not None else (zips[0] if zips else None)
    if inspected_zip is None:
        return ML4RefactoringInspection(dataset_path, len(zips), first_zips, None, None, 0, 0, 0, [], [])

    project_temp_dir = Path(temp_dir) / f"inspect-{inspected_zip.stem}"
    clean_project_temp_dir(project_temp_dir)
    try:
        safe_extract_zip(inspected_zip, project_temp_dir)
        storage_dir = find_project_storage_dir(project_temp_dir)
        if storage_dir is None:
            return ML4RefactoringInspection(dataset_path, len(zips), first_zips, inspected_zip, None, 0, 0, 0, [], [])

        commit_dirs = sorted(path for path in storage_dir.iterdir() if path.is_dir())
        before_after_commits = 0
        candidates: list[Path] = []
        for commit_dir in commit_dirs:
            before_dir = commit_dir / "before-refactoring"
            after_dir = commit_dir / "after-refactoring"
            if before_dir.is_dir() and after_dir.is_dir():
                before_after_commits += 1
                candidates.extend(path for path in before_dir.rglob("*") if is_candidate_code_file(path))
                candidates.extend(path for path in after_dir.rglob("*") if is_candidate_code_file(path))

        sample_files = [path.name for path in candidates[:20]]
        sample_types = [(name, extract_refactoring_type(name)) for name in sample_files[:10]]
        return ML4RefactoringInspection(
            dataset_dir=dataset_path,
            project_zip_count=len(zips),
            first_project_zips=first_zips,
            inspected_zip=inspected_zip,
            project_name=project_name_from_storage(storage_dir),
            commit_count=len(commit_dirs),
            before_after_commit_count=before_after_commits,
            candidate_file_count=len(candidates),
            sample_files=sample_files,
            sample_refactoring_types=sample_types,
        )
    finally:
        clean_project_temp_dir(project_temp_dir)
