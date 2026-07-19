from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from llm_ontology.core.config import read_yaml


class UsageRole(StrEnum):
    RETRIEVAL = "retrieval"
    VALIDATION = "validation"
    PILOT_VALIDATION = "pilot_validation"
    BENCHMARK = "benchmark"


class GroupLevel(StrEnum):
    METHOD = "method"
    COMMIT = "commit"
    PROJECT = "project"
    REPOSITORY = "repository"


class SplitGroupingPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    primary_group_level: GroupLevel
    group_fields: list[str]
    related_case_fields: list[str] = Field(default_factory=list)
    require_cross_role_disjointness: bool = True
    audit_report_path: str


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_name: str
    dataset_version: str | None = None
    source_path: str
    source_split: str
    usage_role: UsageRole
    allowed_for_indexing: bool
    sample_count: int | None = Field(default=None, ge=0)
    content_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    fingerprints_path: str | None = None
    grouping_policy: SplitGroupingPolicy | None = None

    @computed_field
    @property
    def manifest_id(self) -> str:
        identity = "|".join(
            (
                self.dataset_name,
                self.dataset_version or "",
                self.source_path,
                self.source_split,
                self.usage_role.value,
                self.content_hash,
                (
                    self.grouping_policy.model_dump_json()
                    if self.grouping_policy is not None
                    else ""
                ),
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def require_indexable(self) -> None:
        if not self.allowed_for_indexing:
            raise ValueError(
                f"Dataset manifest {self.dataset_name!r} explicitly forbids indexing."
            )
        if self.usage_role != UsageRole.RETRIEVAL:
            raise ValueError(
                f"Dataset role {self.usage_role.value!r} is not indexable; expected 'retrieval'."
            )


def create_dataset_manifest(
    source_path: str | Path,
    *,
    dataset_name: str,
    dataset_version: str | None,
    source_split: str,
    usage_role: UsageRole,
    allowed_for_indexing: bool,
    sample_count: int | None = None,
    metadata: dict[str, Any] | None = None,
    fingerprints_path: str | None = None,
    grouping_policy: SplitGroupingPolicy | None = None,
) -> DatasetManifest:
    path = Path(source_path)
    digest = _source_digest(path)
    return DatasetManifest(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        source_path=path.as_posix(),
        source_split=source_split,
        usage_role=usage_role,
        allowed_for_indexing=allowed_for_indexing,
        sample_count=sample_count,
        content_hash=digest,
        metadata=metadata or {},
        fingerprints_path=fingerprints_path,
        grouping_policy=grouping_policy,
    )


def write_dataset_manifest(manifest: DatasetManifest, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def read_dataset_manifest(path: str | Path) -> DatasetManifest:
    manifest_path = Path(path)
    if manifest_path.suffix.lower() in {".yaml", ".yml"}:
        return DatasetManifest.model_validate(read_yaml(manifest_path))
    return DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def _source_digest(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
        for candidate in files:
            digest.update(candidate.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(candidate.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    raise FileNotFoundError(f"Dataset source does not exist: {path}")
