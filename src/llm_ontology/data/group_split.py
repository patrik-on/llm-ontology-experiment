from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from llm_ontology.ingestion.manifest import DatasetManifest, GroupLevel


T = TypeVar("T")
GroupKey = tuple[str, ...]


class PartitionRecords(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: DatasetManifest
    records: list[dict[str, Any]]


class GroupLocation(BaseModel):
    manifest_id: str
    dataset_name: str
    source_split: str
    usage_role: str
    record_count: int


class GroupOverlap(BaseModel):
    group_level: GroupLevel
    group_key: list[str]
    locations: list[GroupLocation]


class GroupSplitAuditReport(BaseModel):
    group_level: GroupLevel
    partitions: int
    records: int
    overlaps: list[GroupOverlap] = Field(default_factory=list)
    missing_group_records: list[str] = Field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.overlaps and not self.missing_group_records

    def require_safe(self) -> None:
        if not self.safe:
            raise ValueError(
                f"Group split audit failed: {len(self.overlaps)} overlap(s), "
                f"{len(self.missing_group_records)} record(s) without a group identity."
            )


def audit_group_disjointness(
    partitions: Sequence[PartitionRecords],
    *,
    group_level: GroupLevel,
) -> GroupSplitAuditReport:
    locations: dict[GroupKey, dict[str, GroupLocation]] = defaultdict(dict)
    missing: list[str] = []
    total_records = 0
    for partition in partitions:
        manifest = partition.manifest
        for index, record in enumerate(partition.records):
            total_records += 1
            try:
                key = record_group_key(record, group_level)
            except ValueError:
                missing.append(f"{manifest.manifest_id}:record={index}")
                continue
            location_key = "|".join(
                (manifest.manifest_id, manifest.source_split, manifest.usage_role.value)
            )
            current = locations[key].get(location_key)
            if current is None:
                locations[key][location_key] = GroupLocation(
                    manifest_id=manifest.manifest_id,
                    dataset_name=manifest.dataset_name,
                    source_split=manifest.source_split,
                    usage_role=manifest.usage_role.value,
                    record_count=1,
                )
            else:
                current.record_count += 1
    overlaps = [
        GroupOverlap(
            group_level=group_level,
            group_key=list(key),
            locations=list(group_locations.values()),
        )
        for key, group_locations in sorted(locations.items())
        if len(group_locations) > 1
    ]
    return GroupSplitAuditReport(
        group_level=group_level,
        partitions=len(partitions),
        records=total_records,
        overlaps=overlaps,
        missing_group_records=missing,
    )


def write_group_split_audit(report: GroupSplitAuditReport, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output


def record_group_key(record: Mapping[str, Any], level: GroupLevel) -> GroupKey:
    project = _first(record, "project", "project_id") or _project_from_source(record)
    repository = _first(record, "repository", "repo", "repository_url") or project
    commit = _first(record, "commit_sha", "commit")
    if level == GroupLevel.PROJECT:
        return _required_key("project", repository, project)
    if level == GroupLevel.REPOSITORY:
        return _required_key("repository", repository)
    if level == GroupLevel.COMMIT:
        return _required_key("commit", repository, commit)
    method = _first(record, "method_id", "case_id", "refactoring_id")
    return _required_key("method", repository, project, commit, method)


def grouped_split_by_sizes(
    records: list[T],
    *,
    sizes: Mapping[str, int],
    group_key: Callable[[T], GroupKey],
    seed: int,
) -> dict[str, list[T]]:
    if any(size < 0 for size in sizes.values()) or not sizes:
        raise ValueError("Split sizes must be a non-empty mapping of non-negative values.")
    groups = _groups(records, group_key)
    required_splits = sum(1 for size in sizes.values() if size > 0)
    if len(groups) < required_splits:
        raise ValueError(
            f"Need at least {required_splits} independent groups, found {len(groups)}."
        )
    rng = random.Random(seed)
    items = list(groups.items())
    rng.shuffle(items)
    items.sort(key=lambda item: len(item[1]), reverse=True)
    assigned = {name: [] for name in sizes}
    for _, group in items:
        destination = max(
            sizes,
            key=lambda name: (
                sizes[name] - len(assigned[name]),
                -len(assigned[name]),
            ),
        )
        assigned[destination].extend(group)
    shortages = {
        name: size - len(assigned[name])
        for name, size in sizes.items()
        if len(assigned[name]) < size
    }
    if shortages:
        raise ValueError(
            "Whole-group assignment cannot satisfy requested split sizes; "
            f"collect more independent projects/repositories. Shortages: {shortages}."
        )
    result = {name: values[: sizes[name]] for name, values in assigned.items()}
    _require_no_group_overlap(result, group_key)
    return result


def grouped_split_by_ratios(
    records: list[T],
    *,
    ratios: Mapping[str, float],
    group_key: Callable[[T], GroupKey],
    seed: int,
) -> dict[str, list[T]]:
    if not ratios or any(value < 0 for value in ratios.values()):
        raise ValueError("Split ratios must be non-negative.")
    if abs(sum(ratios.values()) - 1.0) > 1e-8:
        raise ValueError("Split ratios must sum to 1.0.")
    groups = _groups(records, group_key)
    required_splits = sum(1 for ratio in ratios.values() if ratio > 0)
    if len(groups) < required_splits:
        raise ValueError(
            f"Need at least {required_splits} independent groups, found {len(groups)}."
        )
    targets = {name: len(records) * ratio for name, ratio in ratios.items()}
    assigned = {name: [] for name in ratios}
    rng = random.Random(seed)
    items = list(groups.items())
    rng.shuffle(items)
    items.sort(key=lambda item: len(item[1]), reverse=True)
    for _, group in items:
        destination = max(
            ratios,
            key=lambda name: targets[name] - len(assigned[name]),
        )
        assigned[destination].extend(group)
    _require_no_group_overlap(assigned, group_key)
    return assigned


def _groups(records: list[T], group_key: Callable[[T], GroupKey]) -> dict[GroupKey, list[T]]:
    groups: dict[GroupKey, list[T]] = defaultdict(list)
    for record in records:
        groups[group_key(record)].append(record)
    return groups


def _require_no_group_overlap(
    splits: Mapping[str, list[T]], group_key: Callable[[T], GroupKey]
) -> None:
    owners: dict[GroupKey, str] = {}
    for split, records in splits.items():
        for record in records:
            key = group_key(record)
            previous = owners.setdefault(key, split)
            if previous != split:
                raise AssertionError(f"Group {key!r} leaked between {previous!r} and {split!r}.")


def _first(record: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = str(record.get(field, "")).strip()
        if value:
            return value.lower()
    return ""


def _project_from_source(record: Mapping[str, Any]) -> str:
    source = str(record.get("source_file", "")).strip()
    return Path(source).parent.name.lower() if source else ""


def _required_key(label: str, *values: str) -> GroupKey:
    non_empty = tuple(value for value in values if value)
    if not non_empty:
        raise ValueError(f"Record has no usable {label} group identity.")
    return non_empty
