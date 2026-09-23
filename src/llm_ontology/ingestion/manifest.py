from __future__ import annotations

import hashlib
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
    SMOKE_EVALUATION = "smoke_evaluation"


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
    source_paths: list[str] = Field(default_factory=list)
    source_split: str
    usage_role: UsageRole
    allowed_for_indexing: bool
    sample_count: int | None = Field(default=None, ge=0)
    case_count: int | None = Field(default=None, ge=0)
    content_hash: str
    schema_version: str = "1"
    tasks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    fingerprints_path: str | None = None
    grouping_policy: SplitGroupingPolicy | None = None

    @computed_field
    @property
    def manifest_id(self) -> str:
        source_identity = self.source_path
        if self.source_paths:
            source_identity += "|" + "|".join(self.source_paths)
        schema_identity = ""
        if self.source_paths or self.tasks or self.schema_version != "1":
            schema_identity = "|".join((self.schema_version, *self.tasks))
        identity = "|".join(
            (
                self.dataset_name,
                self.dataset_version or "",
                source_identity,
                self.source_split,
                self.usage_role.value,
                self.content_hash,
                schema_identity,
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

    def require_source_matches(self, *, root: str | Path | None = None) -> Path:
        declared_sources = self.source_paths or [self.source_path]
        resolved_sources = []
        for declared in declared_sources:
            source = Path(declared)
            if root is not None and not source.is_absolute():
                source = Path(root) / source
            resolved_sources.append(source)
        actual_hash = (
            _source_set_digest(declared_sources, resolved_sources)
            if self.source_paths
            else _source_digest(resolved_sources[0])
        )
        if actual_hash != self.content_hash:
            raise ValueError(
                f"Dataset source hash mismatch for {self.dataset_name!r}: "
                f"expected {self.content_hash}, got {actual_hash}."
            )
        if self.sample_count is not None and all(source.is_file() for source in resolved_sources):
            actual_count = 0
            for source in resolved_sources:
                with source.open("r", encoding="utf-8") as handle:
                    actual_count += sum(1 for line in handle if line.strip())
            if actual_count != self.sample_count:
                raise ValueError(
                    f"Dataset sample count mismatch for {self.dataset_name!r}: "
                    f"expected {self.sample_count}, got {actual_count}."
                )
        return resolved_sources[0]


def create_dataset_manifest(
    source_path: str | Path,
    *,
    dataset_name: str,
    dataset_version: str | None,
    source_split: str,
    usage_role: UsageRole,
    allowed_for_indexing: bool,
    sample_count: int | None = None,
    case_count: int | None = None,
    metadata: dict[str, Any] | None = None,
    fingerprints_path: str | None = None,
    grouping_policy: SplitGroupingPolicy | None = None,
    source_paths: list[str] | None = None,
    schema_version: str = "1",
    tasks: list[str] | None = None,
) -> DatasetManifest:
    path = Path(source_path)
    declared_sources = source_paths or []
    resolved_sources = [Path(source) for source in declared_sources]
    digest = (
        _source_set_digest(declared_sources, resolved_sources)
        if declared_sources
        else _source_digest(path)
    )
    return DatasetManifest(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        source_path=path.as_posix(),
        source_paths=declared_sources,
        source_split=source_split,
        usage_role=usage_role,
        allowed_for_indexing=allowed_for_indexing,
        sample_count=sample_count,
        case_count=case_count,
        content_hash=digest,
        schema_version=schema_version,
        tasks=tasks or [],
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


def _source_set_digest(declared: list[str], resolved: list[Path]) -> str:
    if len(declared) != len(resolved):
        raise ValueError("Declared and resolved source lists must have equal length.")
    digest = hashlib.sha256()
    for name, path in sorted(zip(declared, resolved, strict=True), key=lambda item: item[0]):
        if not path.is_file():
            raise FileNotFoundError(f"Dataset source does not exist: {path}")
        digest.update(Path(name).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
