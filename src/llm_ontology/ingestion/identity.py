from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from llm_ontology.retrieval.models import normalize_content, sha256_text


class CaseIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset: str
    case_id: str = ""
    repository: str = ""
    commit: str = ""
    file_path: str = ""
    class_name: str = ""
    method_name: str = ""

    @property
    def canonical_key(self) -> str:
        parts = (
            self.dataset,
            self.case_id,
            self.repository,
            self.commit,
            self.file_path.replace(chr(92), "/"),
            self.class_name,
            self.method_name,
        )
        return "|".join(part.strip().lower() for part in parts)


class SampleFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: CaseIdentity
    input_code_hash: str
    focal_method_hash: str
    full_document_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeakageMatch(BaseModel):
    indexed_identity: CaseIdentity
    benchmark_identity: CaseIdentity
    matched_by: list[str]


class LeakageReport(BaseModel):
    indexed_manifest_id: str
    benchmark_manifest_id: str
    indexed_samples: int
    benchmark_samples: int
    overlaps: list[LeakageMatch] = Field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.overlaps

    def require_safe(self) -> None:
        if self.overlaps:
            raise ValueError(
                f"Detected {len(self.overlaps)} overlap(s) between retrieval and benchmark data."
            )


def normalize_java_for_hash(code: str) -> str:
    """Create a conservative lexical fingerprint without changing string literals."""

    token_pattern = re.compile(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/|'
        r"[A-Za-z_$][A-Za-z0-9_$]*|\d+(?:\.\d+)?|\S",
        re.DOTALL,
    )
    tokens = []
    normalized_newlines = code.replace(chr(13) + chr(10), chr(10))
    for match in token_pattern.finditer(normalized_newlines):
        token = match.group(0)
        if token.startswith("//") or token.startswith("/*"):
            continue
        tokens.append(token)
    return " ".join(tokens)


def java_code_hash(code: str) -> str:
    return sha256_text(normalize_java_for_hash(code))


def make_pair_id(kind: str, identity: CaseIdentity, input_code: str, output_code: str) -> str:
    value = "|".join(
        (
            kind,
            identity.canonical_key,
            java_code_hash(input_code),
            java_code_hash(output_code),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_sample_fingerprint(
    *,
    identity: CaseIdentity,
    input_code: str,
    full_document: str,
    focal_method_code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SampleFingerprint:
    return SampleFingerprint(
        identity=identity,
        input_code_hash=java_code_hash(input_code),
        focal_method_hash=java_code_hash(focal_method_code or input_code),
        full_document_hash=sha256_text(normalize_content(full_document)),
        metadata=metadata or {},
    )


def detect_leakage(
    indexed: Iterable[SampleFingerprint],
    benchmark: Iterable[SampleFingerprint],
    *,
    indexed_manifest_id: str,
    benchmark_manifest_id: str,
) -> LeakageReport:
    indexed_items = list(indexed)
    benchmark_items = list(benchmark)
    overlaps: list[LeakageMatch] = []
    for indexed_item in indexed_items:
        for benchmark_item in benchmark_items:
            matched_by = _matching_fields(indexed_item, benchmark_item)
            if matched_by:
                overlaps.append(
                    LeakageMatch(
                        indexed_identity=indexed_item.identity,
                        benchmark_identity=benchmark_item.identity,
                        matched_by=matched_by,
                    )
                )
    return LeakageReport(
        indexed_manifest_id=indexed_manifest_id,
        benchmark_manifest_id=benchmark_manifest_id,
        indexed_samples=len(indexed_items),
        benchmark_samples=len(benchmark_items),
        overlaps=overlaps,
    )


def _matching_fields(left: SampleFingerprint, right: SampleFingerprint) -> list[str]:
    fields = []
    if left.input_code_hash == right.input_code_hash:
        fields.append("input_code_hash")
    if left.focal_method_hash == right.focal_method_hash:
        fields.append("focal_method_hash")
    if left.full_document_hash == right.full_document_hash:
        fields.append("full_document_hash")
    if _identity_is_specific(left.identity) and left.identity.canonical_key == right.identity.canonical_key:
        fields.append("structured_identity")
    return fields


def _identity_is_specific(identity: CaseIdentity) -> bool:
    return bool(
        identity.case_id
        or (identity.repository and identity.commit and identity.file_path)
        or (identity.repository and identity.class_name and identity.method_name)
    )


def write_fingerprints(items: Iterable[SampleFingerprint], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.model_dump_json() + chr(10))


def read_fingerprints(path: str | Path) -> list[SampleFingerprint]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [SampleFingerprint.model_validate(json.loads(line)) for line in handle if line.strip()]


def write_leakage_report(report: LeakageReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
