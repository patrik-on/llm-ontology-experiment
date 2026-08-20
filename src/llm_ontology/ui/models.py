from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from llm_ontology.retrieval.models import RetrievalMode

TASK_LABELS: dict[str, str] = {
    "Testing": "testing",
    "Refactoring": "refactoring",
}

MODE_LABELS: dict[str, RetrievalMode] = {
    "Direct LLM": RetrievalMode.NO_RAG,
    "RAG": RetrievalMode.SINGLE_COLLECTION_RAG,
    "MultiRAG": RetrievalMode.MULTI_COLLECTION_RAG,
}

LEGACY_MODE_LABELS: dict[str, RetrievalMode] = {
    "MultiRAG (Not available yet)": RetrievalMode.MULTI_COLLECTION_RAG,
}


def task_from_label(label: str) -> str:
    try:
        return TASK_LABELS[label]
    except KeyError as exc:
        raise ValueError(f"Unknown UI task: {label!r}.") from exc


def mode_from_label(label: str) -> RetrievalMode:
    try:
        return MODE_LABELS[label]
    except KeyError as exc:
        try:
            return LEGACY_MODE_LABELS[label]
        except KeyError:
            raise ValueError(f"Unknown UI mode: {label!r}.") from exc


class UIRunRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: Literal["testing", "refactoring"]
    mode: RetrievalMode
    source_code: str
    requirements: str = ""
    top_k: int = Field(default=5, ge=1, le=100)
    log_level: Literal["INFO", "DEBUG"] = "INFO"

    @field_validator("source_code")
    @classmethod
    def source_code_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Java input must not be empty.")
        return value

    @field_validator("requirements")
    @classmethod
    def normalize_requirements(cls, value: str) -> str:
        return value.strip()


class GeneratedOutputView(BaseModel):
    code: str = ""
    summary: str = ""
    detected_code_smells: list[str] = Field(default_factory=list)
    applied_refactorings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class RetrievalDocumentView(BaseModel):
    rank: int
    document_id: str
    collection: str
    source_collections: str = "N/A"
    original_ranks: str = "N/A"
    rrf_score: float | str = "N/A"
    final_rank: int | str = "N/A"
    source_type: str = "N/A"
    dataset_name: str = "N/A"
    score: float | str = "N/A"
    class_name: str = "N/A"
    method_name: str = "N/A"
    source_path: str = "N/A"
    used_in_prompt: bool = False
    preview: str = ""
    content: str = ""


class PromptView(BaseModel):
    final_prompt: str = ""
    prompt_hash: str = "N/A"
    prompt_tokens: int | str = "N/A"
    retrieval_tokens: int | str = "N/A"
    counting_method: str = "N/A"
    artifact_path: str = "N/A"


class MetricsView(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class UIRunView(BaseModel):
    success: bool
    run_id: str
    status: str
    output: GeneratedOutputView = Field(default_factory=GeneratedOutputView)
    retrieval_message: str = ""
    retrieval_documents: list[RetrievalDocumentView] = Field(default_factory=list)
    fusion_trace: dict[str, Any] = Field(default_factory=dict)
    prompt: PromptView = Field(default_factory=PromptView)
    metrics: MetricsView = Field(default_factory=MetricsView)
    logs: str = ""
    error: str | None = None


class CollectionStatus(BaseModel):
    name: str
    document_count: int | str = "N/A"
    embedding_provider: str = "N/A"
    embedding_model: str = "N/A"
    embedding_revision: str = "N/A"
    embedding_model_digest: str = "N/A"
    embedding_dimension: int | str = "N/A"
    ollama_runtime: str = "N/A"
    chunker_version: str = "N/A"
    manifest_status: str = "missing"


class EnvironmentStatus(BaseModel):
    status: str = "NOT_READY"
    runtime_os: str = "N/A"
    runtime_environment: str = "N/A"
    ollama_status: str
    ollama_base_url: str = "N/A"
    configured_model: str
    model_available: bool
    model_digest: str = "N/A"
    chroma_path: str
    chroma_status: str
    embedding_provider: str = "N/A"
    embedding_model: str
    embedding_revision: str
    embedding_model_digest: str = "N/A"
    embedding_dimension: int | str = "N/A"
    embedding_base_url: str = "N/A"
    embedding_status: str = "N/A"
    generation_provider: str = "N/A"
    generation_model: str = "N/A"
    generation_model_digest: str = "N/A"
    generation_status: str = "N/A"
    python_version: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    collections: list[CollectionStatus] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
