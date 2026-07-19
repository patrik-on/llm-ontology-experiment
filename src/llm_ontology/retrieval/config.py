from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from llm_ontology.core.config import read_yaml
from llm_ontology.retrieval.models import RetrievalMode, Scalar


class CollectionSettings(BaseModel):
    refactor: str = "refactor"
    tests: str = "tests"
    mixed: str = "mixed"
    refactoring_examples: str = "refactoring_examples"
    test_examples: str = "test_examples"
    software_engineering_literature: str = "software_engineering_literature"
    ontology_concepts: str = "ontology_concepts"
    project_context: str | None = "project_context"

    @model_validator(mode="after")
    def collection_names_must_be_unique(self) -> CollectionSettings:
        values = [value for value in self.model_dump().values() if value is not None]
        if len(values) != len(set(values)):
            raise ValueError("ChromaDB collection names must be unique.")
        return self

    def resolve(self, logical_name: str) -> str:
        try:
            value = getattr(self, logical_name)
        except AttributeError as exc:
            raise ValueError(f"Unknown logical collection: {logical_name}") from exc
        if value is None:
            raise ValueError(f"Collection {logical_name!r} is disabled.")
        return value


class EmbeddingSettings(BaseModel):
    provider: str = "deterministic_mock"
    model: str = "deterministic-hash-embedding"
    version: str = "1"
    revision: str | None = None
    remote_code_revision: str | None = None
    dimension: int = Field(default=64, ge=8)
    normalized: bool = True
    device: str = "cpu"
    batch_size: int = Field(default=16, ge=1)
    max_sequence_length: int | None = Field(default=None, ge=8)
    trust_remote_code: bool = False
    deterministic: bool = True
    candidate_status: str = "test_only"


class LLMSettings(BaseModel):
    provider: str = "mock"
    model: str = "mock-llm"
    version: str = "1"
    mock_response: str = '{"analysis_summary":"mock response"}'
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    seed: int | None = 42
    timeout_seconds: float = Field(default=120.0, gt=0.0)


class VectorStoreSettings(BaseModel):
    provider: str = "chromadb"
    persist_path: Path = Path("data/chroma")
    distance: str = "cosine"

    @field_validator("distance")
    @classmethod
    def supported_distance(cls, value: str) -> str:
        if value != "cosine":
            raise ValueError("Phase 1 currently supports only cosine distance.")
        return value


class IngestionSettings(BaseModel):
    allowed_splits: list[str] = Field(default_factory=lambda: ["train"])
    pipeline_version: str = "rag-v1"
    literature_max_chars: int = Field(default=1800, ge=200)


class RetrievalSettings(BaseModel):
    mode: RetrievalMode = RetrievalMode.SINGLE_COLLECTION_RAG
    top_k: int = Field(default=3, ge=1, le=100)
    max_context_tokens: int = Field(default=2048, ge=1)
    allowed_splits: list[str] = Field(default_factory=lambda: ["train"])
    collections: list[str] = Field(default_factory=list)
    metadata_filter: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)


class ExperimentSettings(BaseModel):
    results_path: Path = Path("experiments/results/rag_runs.jsonl")
    random_seed: int = 42


class RagConfig(BaseModel):
    collections: CollectionSettings = Field(default_factory=CollectionSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    experiment: ExperimentSettings = Field(default_factory=ExperimentSettings)


def load_rag_config(path: str | Path) -> RagConfig:
    payload = read_yaml(path)
    return RagConfig.model_validate(payload)
