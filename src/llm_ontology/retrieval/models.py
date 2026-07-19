from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


PIPELINE_VERSION = "rag-v1"
Scalar = str | int | float | bool


class DocumentType(StrEnum):
    REFACTORING_EXAMPLE = "refactoring_example"
    TEST_EXAMPLE = "test_example"
    LITERATURE = "literature"
    ONTOLOGY_CONCEPT = "ontology_concept"
    PROJECT_CONTEXT = "project_context"


class RetrievalMode(StrEnum):
    NO_RAG = "no_rag"
    SINGLE_COLLECTION_RAG = "single_collection_rag"
    METADATA_RAG = "metadata_rag"
    MULTI_COLLECTION_RAG = "multi_collection_rag"
    ONTOLOGY_ENHANCED_RAG = "ontology_enhanced_rag"


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    embedding_text: str
    document_type: DocumentType
    collection: str
    source: str
    dataset: str
    split: str = "train"
    language: str = ""
    task: str = ""
    source_uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content", "embedding_text", "collection", "source", "dataset", "source_uri")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value


class DocumentChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    content: str
    embedding_text: str
    document_type: DocumentType
    collection: str
    source: str
    dataset: str
    split: str
    language: str = ""
    task: str = ""
    source_uri: str
    pipeline_version: str = PIPELINE_VERSION
    content_hash: str
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def chroma_metadata(self) -> dict[str, Scalar]:
        metadata: dict[str, Scalar] = {
            "document_type": self.document_type.value,
            "source": self.source,
            "dataset": self.dataset,
            "split": self.split,
            "language": self.language,
            "task": self.task,
            "source_uri": self.source_uri,
            "pipeline_version": self.pipeline_version,
            "content_hash": self.content_hash,
            "chunk_index": self.chunk_index,
        }
        domain_metadata: dict[str, Any] = {}
        for key, value in self.metadata.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value
            elif value is not None:
                domain_metadata[key] = value
        if domain_metadata:
            metadata["domain_metadata_json"] = json.dumps(
                domain_metadata, ensure_ascii=False, sort_keys=True
            )
        return metadata


class RetrievalRequest(BaseModel):
    query: str
    mode: RetrievalMode = RetrievalMode.SINGLE_COLLECTION_RAG
    collections: list[str] = Field(default_factory=list)
    metadata_filter: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)
    allowed_splits: list[str] = Field(default_factory=lambda: ["train"])
    top_k: int = Field(default=3, ge=1, le=100)
    max_context_tokens: int = Field(default=2048, ge=1)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank.")
        return value.strip()


class RetrievalHit(BaseModel):
    document_id: str
    collection: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    reranking_score: float | None = None


class RetrievalTrace(BaseModel):
    query: str
    transformed_queries: list[str] = Field(default_factory=list)
    selected_collections: list[str] = Field(default_factory=list)
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    retrieved_documents: list[RetrievalHit] = Field(default_factory=list)
    prompt_document_ids: list[str] = Field(default_factory=list)
    ontology_concepts: list[str] = Field(default_factory=list)
    estimated_context_tokens: int = 0
    step_latency_ms: dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0


class RetrievalResult(BaseModel):
    documents: list[RetrievalHit] = Field(default_factory=list)
    trace: RetrievalTrace


class RetrievedEvidence(BaseModel):
    document_id: str
    collection: str
    source_type: str
    score: float | None = None
    relevance: str = ""


class ValidationResult(BaseModel):
    valid: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    details: list[str] = Field(default_factory=list)


class RagAnswer(BaseModel):
    task_type: str = ""
    analysis_summary: str = ""
    detected_code_smells: list[str] = Field(default_factory=list)
    recommended_refactorings: list[str] = Field(default_factory=list)
    refactored_code: str | None = None
    generated_tests: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieved_evidence: list[RetrievedEvidence] = Field(default_factory=list)
    ontology_concepts: list[str] = Field(default_factory=list)
    validation_result: ValidationResult | None = None


def normalize_content(content: str) -> str:
    lines = [re.sub(r"[ \t]+$", "", line) for line in content.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def sha256_text(content: str) -> str:
    return hashlib.sha256(normalize_content(content).encode("utf-8")).hexdigest()


def make_document_chunk(
    document: SourceDocument,
    *,
    content: str | None = None,
    embedding_text: str | None = None,
    chunk_index: int = 0,
    metadata: dict[str, Any] | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> DocumentChunk:
    chunk_content = content if content is not None else document.content
    chunk_embedding_text = embedding_text if embedding_text is not None else document.embedding_text
    content_hash = sha256_text(chunk_content)
    identity = "|".join(
        (
            document.dataset,
            document.split,
            document.source_uri,
            str(chunk_index),
            pipeline_version,
            content_hash,
        )
    )
    document_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return DocumentChunk(
        document_id=document_id,
        content=chunk_content,
        embedding_text=chunk_embedding_text,
        document_type=document.document_type,
        collection=document.collection,
        source=document.source,
        dataset=document.dataset,
        split=document.split,
        language=document.language,
        task=document.task,
        source_uri=document.source_uri,
        pipeline_version=pipeline_version,
        content_hash=content_hash,
        chunk_index=chunk_index,
        metadata={**document.metadata, **(metadata or {})},
    )
