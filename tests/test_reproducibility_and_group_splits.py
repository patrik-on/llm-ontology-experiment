from __future__ import annotations

import json
import hashlib
import importlib.metadata
import sys
from pathlib import Path

import pytest

from llm_ontology.core.environment_lock import verify_environment_lock
from llm_ontology.data.group_split import (
    PartitionRecords,
    audit_group_disjointness,
    grouped_split_by_sizes,
    record_group_key,
)
from llm_ontology.data.methods2test import require_project_disjoint_official_splits
from llm_ontology.data.ml4refactoring import split_records as split_ml4_records
from llm_ontology.ingestion.manifest import (
    DatasetManifest,
    GroupLevel,
    UsageRole,
    read_dataset_manifest,
)


def test_environment_lock_verifier_checks_exact_python_and_packages(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.lock.txt"
    requirements.write_text(
        f"pydantic=={importlib.metadata.version('pydantic')}\n", encoding="utf-8"
    )
    lock = tmp_path / "environment.json"
    lock.write_text(
        json.dumps(
            {
                "python": {"version": ".".join(str(part) for part in sys.version_info[:3])},
                "python_packages_lock": str(requirements),
                "python_packages_lock_sha256": hashlib.sha256(
                    requirements.read_bytes()
                ).hexdigest(),
                "ollama": {},
            }
        ),
        encoding="utf-8",
    )
    report = verify_environment_lock(lock, check_ollama=False)

    assert report.ready


def test_environment_lock_contains_all_model_revisions() -> None:
    payload = json.loads(
        Path("configs/environment/rag_baseline_windows_cpu.lock.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["embedding"]["revision"] == "516f4baf13dec4ddddda8631e019b5737c8bc250"
    assert payload["embedding"]["remote_code_revision"] == "3baf9e3ac750e76e8edd3019170176884695fb94"
    assert payload["tokenizer"]["revision"] == "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    assert payload["ollama"]["version"] == "0.32.1"
    assert payload["ollama"]["runtime_digest"] is None
    assert payload["status"] == "blocked_missing_runtime_components"


def test_manifest_templates_keep_split_and_role_independent() -> None:
    root = Path("configs/datasets/manifests")
    retrieval = read_dataset_manifest(root / "retrieval.template.yaml")
    pilot = read_dataset_manifest(root / "pilot_validation.template.yaml")
    benchmark = read_dataset_manifest(root / "final_benchmark.template.yaml")

    assert (retrieval.source_split, retrieval.usage_role, retrieval.allowed_for_indexing) == (
        "train",
        UsageRole.RETRIEVAL,
        True,
    )
    assert (pilot.source_split, pilot.usage_role, pilot.allowed_for_indexing) == (
        "validation",
        UsageRole.PILOT_VALIDATION,
        False,
    )
    assert (benchmark.source_split, benchmark.usage_role, benchmark.allowed_for_indexing) == (
        "test",
        UsageRole.BENCHMARK,
        False,
    )


def test_group_audit_detects_project_across_retrieval_and_benchmark() -> None:
    retrieval = _manifest("train", UsageRole.RETRIEVAL, True)
    benchmark = _manifest("test", UsageRole.BENCHMARK, False)
    report = audit_group_disjointness(
        [
            PartitionRecords(manifest=retrieval, records=[{"repository": "org/repo"}]),
            PartitionRecords(manifest=benchmark, records=[{"repository": "org/repo"}]),
        ],
        group_level=GroupLevel.REPOSITORY,
    )

    assert not report.safe
    assert report.overlaps[0].group_key == ["org/repo"]


def test_grouped_split_keeps_all_project_cases_together() -> None:
    records = [
        {"project": project, "case_id": f"{project}-{case}"}
        for project in ("a", "b", "c", "d")
        for case in range(3)
    ]
    splits = grouped_split_by_sizes(
        records,
        sizes={"train": 6, "val": 3, "test": 3},
        group_key=lambda record: record_group_key(record, GroupLevel.PROJECT),
        seed=42,
    )

    owners = {}
    for split, items in splits.items():
        for item in items:
            assert owners.setdefault(item["project"], split) == split


def test_methods2test_rejects_project_overlap_between_official_splits(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    for split in ("train", "eval", "test"):
        directory = root / split / "same-project"
        directory.mkdir(parents=True)
        (directory / f"{split}_corpus.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="project/repository level"):
        require_project_disjoint_official_splits(root)


def test_ml4refactoring_keeps_all_commits_from_project_in_one_split() -> None:
    records = [
        {
            "project": project,
            "commit_sha": f"{project}-commit-{commit}",
            "input": "before",
            "output": "after",
        }
        for project in ("a", "b", "c", "d")
        for commit in range(3)
    ]
    splits = split_ml4_records(records, train_size=6, val_size=3, test_size=3, seed=42)

    owners = {}
    for split, items in splits.items():
        for item in items:
            assert owners.setdefault(item["project"], split) == split


def _manifest(split: str, role: UsageRole, allowed: bool) -> DatasetManifest:
    return DatasetManifest(
        dataset_name=f"dataset-{split}",
        dataset_version="v1",
        source_path=f"{split}.jsonl",
        source_split=split,
        usage_role=role,
        allowed_for_indexing=allowed,
        sample_count=1,
        content_hash="a" * 64,
    )
