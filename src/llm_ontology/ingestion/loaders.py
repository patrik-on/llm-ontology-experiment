from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from llm_ontology.data.format import read_records
from llm_ontology.ingestion.documents import (
    DocumentRelationship,
    KnowledgeDocument,
    materialize_for_collection,
)
from llm_ontology.ingestion.identity import (
    CaseIdentity,
    make_pair_id,
    make_sample_fingerprint,
)
from llm_ontology.ingestion.manifest import DatasetManifest, UsageRole
from llm_ontology.retrieval.models import DocumentType, SourceDocument


class NormalizedJsonlLoader:
    """Load the repository's normalized refactoring or testing records."""

    def __init__(
        self,
        path: str | Path,
        *,
        dataset: str,
        collection: str,
        split: str = "train",
        manifest: DatasetManifest | None = None,
        expected_context_level: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.dataset = dataset
        self.collection = collection
        self.split = split
        self.manifest = manifest
        self.expected_context_level = expected_context_level

    def load(self) -> Iterable[SourceDocument]:
        for document in self.load_knowledge():
            yield materialize_for_collection(document, self.collection)

    def load_knowledge(self) -> Iterable[KnowledgeDocument]:
        for index, record in enumerate(read_records(self.path)):
            domain = str(record.get("domain", "")).strip().lower()
            if domain not in {"testing", "refactoring"}:
                raise ValueError(
                    f"Record {index} in {self.path} has unsupported domain {domain!r}."
                )
            input_text = str(record.get("input", "")).strip()
            output_text = str(record.get("output", "")).strip()
            if not input_text or not output_text:
                raise ValueError(f"Record {index} in {self.path} needs non-empty input and output.")
            instruction = str(record.get("instruction", "")).strip()
            source = str(record.get("source", self.dataset)).strip() or self.dataset
            document_type = (
                DocumentType.TEST_EXAMPLE
                if domain == "testing"
                else DocumentType.REFACTORING_EXAMPLE
            )
            source_ref = str(record.get("source_file", "")).strip()
            source_uri = source_ref or f"{self.path.as_posix()}#record={index}"
            source_split = self.manifest.source_split if self.manifest else self.split
            usage_role = (
                self.manifest.usage_role.value if self.manifest else UsageRole.RETRIEVAL.value
            )
            case_identity = _case_identity(record, self.dataset, index, source_uri)
            full_content = json.dumps(record, ensure_ascii=False, sort_keys=True)
            fingerprint = make_sample_fingerprint(
                identity=case_identity,
                input_code=input_text,
                focal_method_code=input_text,
                full_document=full_content,
            )
            metadata = _metadata_without(record, {"instruction", "input", "output"})
            metadata.update(
                {
                    "instruction": instruction,
                    "input_code": input_text,
                    "output_code": output_text,
                    "input_code_hash": fingerprint.input_code_hash,
                    "focal_method_hash": fingerprint.focal_method_hash,
                    "full_document_hash": fingerprint.full_document_hash,
                }
            )
            relationships: list[DocumentRelationship] = []
            if domain == "refactoring":
                pair_id = make_pair_id("refactoring", case_identity, input_text, output_text)
                metadata["refactoring_pair_id"] = pair_id
                metadata["original_method_id"] = _code_id("original", input_text)
                metadata["refactored_method_id"] = _code_id("refactored", output_text)
                relationships.append(
                    DocumentRelationship(
                        relationship_type="refactored_to",
                        target_id=str(metadata["refactored_method_id"]),
                    )
                )
            else:
                context_level = str(record.get("context_level", "src_fm"))
                if self.expected_context_level and context_level != self.expected_context_level:
                    raise ValueError(
                        f"Record {index} uses context level {context_level!r}; "
                        f"expected {self.expected_context_level!r}."
                    )
                pair_id = make_pair_id("testing", case_identity, input_text, output_text)
                metadata["context_level"] = context_level
                metadata["test_pair_id"] = pair_id
                metadata["production_method_id"] = _code_id("production", input_text)
                metadata["test_method_id"] = _code_id("test", output_text)
                relationships.append(
                    DocumentRelationship(
                        relationship_type="tested_by",
                        target_id=str(metadata["test_method_id"]),
                    )
                )
            yield KnowledgeDocument(
                content=full_content,
                document_type=document_type,
                source=source,
                dataset=self.dataset,
                source_split=source_split,
                usage_role=usage_role,
                language="java",
                task=domain,
                source_uri=source_uri,
                identity=case_identity,
                metadata=metadata,
                relationships=relationships,
            )


class TextDocumentLoader:
    """Load UTF-8 TXT or Markdown literature as one source document."""

    SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}

    def __init__(
        self,
        path: str | Path,
        *,
        dataset: str,
        collection: str,
        split: str = "train",
        metadata: dict[str, Any] | None = None,
        manifest: DatasetManifest | None = None,
    ) -> None:
        self.path = Path(path)
        self.dataset = dataset
        self.collection = collection
        self.split = split
        self.metadata = metadata or {}
        self.manifest = manifest

    def load(self) -> Iterable[SourceDocument]:
        for document in self.load_knowledge():
            yield materialize_for_collection(document, self.collection)

    def load_knowledge(self) -> Iterable[KnowledgeDocument]:
        if self.path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            supported = ", ".join(sorted(self.SUPPORTED_SUFFIXES))
            raise ValueError(f"Unsupported literature format. Phase 1 supports: {supported}.")
        content = self.path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Literature document is empty: {self.path}")
        source_split = self.manifest.source_split if self.manifest else self.split
        usage_role = self.manifest.usage_role.value if self.manifest else UsageRole.RETRIEVAL.value
        yield KnowledgeDocument(
            content=content,
            document_type=DocumentType.LITERATURE,
            source=self.path.name,
            dataset=self.dataset,
            source_split=source_split,
            usage_role=usage_role,
            task="software_engineering_literature",
            source_uri=self.path.as_posix(),
            identity=CaseIdentity(
                dataset=self.dataset,
                case_id=self.path.name,
                file_path=self.path.as_posix(),
            ),
            metadata={
                "title": self.path.stem,
                "document_title": self.path.stem,
                "source_path": self.path.as_posix(),
                "section_title": "",
                "loader_name": "utf8_text",
                "loader_version": "1",
                **self.metadata,
            },
        )


def _metadata_without(record: dict[str, Any], excluded: set[str]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in excluded}


def _case_identity(
    record: dict[str, Any], dataset: str, index: int, source_uri: str
) -> CaseIdentity:
    return CaseIdentity(
        dataset=dataset,
        case_id=str(record.get("id") or record.get("case_id") or f"record-{index}"),
        repository=str(record.get("repository") or record.get("project") or ""),
        commit=str(record.get("commit_sha") or record.get("commit") or ""),
        file_path=str(record.get("file_path") or record.get("source_file") or source_uri),
        class_name=str(record.get("class_name") or ""),
        method_name=str(record.get("method_name") or ""),
    )


def _code_id(role: str, code: str) -> str:
    return hashlib.sha256(f"{role}|{code.strip()}".encode("utf-8")).hexdigest()
