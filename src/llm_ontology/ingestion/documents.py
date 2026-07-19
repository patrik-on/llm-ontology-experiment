from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, computed_field

from llm_ontology.ingestion.identity import CaseIdentity
from llm_ontology.retrieval.models import DocumentType, SourceDocument, sha256_text


class DocumentRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    relationship_type: str
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocument(BaseModel):
    """Collection-independent semantic document produced by ingestion."""

    model_config = ConfigDict(frozen=True)

    content: str
    document_type: DocumentType
    source: str
    dataset: str
    source_split: str
    usage_role: str
    task: str = ""
    language: str = ""
    source_uri: str
    identity: CaseIdentity
    metadata: dict[str, Any] = Field(default_factory=dict)
    relationships: list[DocumentRelationship] = Field(default_factory=list)

    @computed_field
    @property
    def content_hash(self) -> str:
        return sha256_text(self.content)

    @computed_field
    @property
    def document_id(self) -> str:
        identity = "|".join(
            (
                self.dataset,
                self.source_split,
                self.source_uri,
                self.identity.canonical_key,
                self.content_hash,
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class EmbeddingText(BaseModel):
    text: str
    template_name: str
    template_version: str


@runtime_checkable
class EmbeddingTextBuilder(Protocol):
    template_name: str
    template_version: str

    def build(self, document: KnowledgeDocument) -> EmbeddingText:
        """Build versioned semantic text without technical provenance noise."""


class RefactoringEmbeddingTextBuilder:
    template_name = "refactoring_pair"
    template_version = "1"

    def build(self, document: KnowledgeDocument) -> EmbeddingText:
        before = str(document.metadata.get("input_code", "")).strip()
        after = str(document.metadata.get("output_code", "")).strip()
        refactoring_type = str(document.metadata.get("refactoring_type", "unknown"))
        diff = str(document.metadata.get("diff", "")).strip()
        parts = [
            "Task: refactoring",
            f"Refactoring type: {refactoring_type}",
            f"Original Java code:\n{before}",
            f"Refactored Java code:\n{after}",
        ]
        if diff:
            parts.append(f"Change summary or diff:\n{diff}")
        return EmbeddingText(
            text="\n\n".join(parts),
            template_name=self.template_name,
            template_version=self.template_version,
        )


class TestingEmbeddingTextBuilder:
    template_name = "production_test_pair"
    template_version = "1"

    def build(self, document: KnowledgeDocument) -> EmbeddingText:
        production = str(document.metadata.get("input_code", "")).strip()
        test_code = str(document.metadata.get("output_code", "")).strip()
        context_level = str(document.metadata.get("context_level", "src_fm"))
        return EmbeddingText(
            text="\n\n".join(
                (
                    "Task: test generation",
                    f"Methods2Test context level: {context_level}",
                    f"Production Java code:\n{production}",
                    f"Corresponding test code:\n{test_code}",
                )
            ),
            template_name=self.template_name,
            template_version=self.template_version,
        )


class LiteratureEmbeddingTextBuilder:
    template_name = "software_engineering_literature"
    template_version = "1"

    def build(self, document: KnowledgeDocument) -> EmbeddingText:
        title = str(document.metadata.get("document_title", document.source)).strip()
        section = str(document.metadata.get("section_title", "")).strip()
        parts = [f"Document: {title}"]
        if section:
            parts.append(f"Section: {section}")
        parts.append(document.content.strip())
        return EmbeddingText(
            text="\n\n".join(parts),
            template_name=self.template_name,
            template_version=self.template_version,
        )


def default_embedding_text_builder(document_type: DocumentType) -> EmbeddingTextBuilder:
    if document_type == DocumentType.REFACTORING_EXAMPLE:
        return RefactoringEmbeddingTextBuilder()
    if document_type == DocumentType.TEST_EXAMPLE:
        return TestingEmbeddingTextBuilder()
    if document_type == DocumentType.LITERATURE:
        return LiteratureEmbeddingTextBuilder()
    raise ValueError(f"No embedding text builder registered for {document_type.value!r}.")


def materialize_for_collection(
    document: KnowledgeDocument,
    collection: str,
    builder: EmbeddingTextBuilder | None = None,
) -> SourceDocument:
    selected_builder = builder or default_embedding_text_builder(document.document_type)
    embedding = selected_builder.build(document)
    embedded_fields = {"input_code", "output_code", "diff", "instruction"}
    public_metadata = {
        key: value for key, value in document.metadata.items() if key not in embedded_fields
    }
    return SourceDocument(
        content=embedding.text,
        embedding_text=embedding.text,
        document_type=document.document_type,
        collection=collection,
        source=document.source,
        dataset=document.dataset,
        split=document.source_split,
        language=document.language,
        task=document.task,
        source_uri=document.source_uri,
        metadata={
            **public_metadata,
            "_input_code": document.metadata.get("input_code", ""),
            "_output_code": document.metadata.get("output_code", ""),
            "knowledge_document_id": document.document_id,
            "usage_role": document.usage_role,
            "embedding_text_template": embedding.template_name,
            "embedding_text_template_version": embedding.template_version,
            "relationships": [relationship.model_dump() for relationship in document.relationships],
        },
    )
