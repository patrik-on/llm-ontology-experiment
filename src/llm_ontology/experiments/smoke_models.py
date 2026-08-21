from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_ontology.core.config import read_yaml
from llm_ontology.retrieval.models import RetrievalMode


SMOKE_MODES = (
    RetrievalMode.NO_RAG,
    RetrievalMode.SINGLE_COLLECTION_RAG,
    RetrievalMode.MULTI_COLLECTION_RAG,
)


class FrozenCollectionIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_count: int = Field(ge=1)
    dataset_manifest_ids: tuple[str, ...]


class SmokeExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_name: str = "baseline_v1"
    baseline_id: str = "baseline_v1"
    baseline_contract_version: str = "1"
    baseline_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_root: Path = Path("data/smoke")
    retrieval_config: Path = Path("configs/retrieval/ollama_bge_m3.yaml")
    output_dir: Path = Path("artifacts/experiments/smoke/baseline_v1")
    modes: tuple[RetrievalMode, ...] = SMOKE_MODES
    single_collection: str = "mixed"
    multi_collections: tuple[str, ...] = ("testing_db", "refactoring_db")
    allowed_splits: tuple[str, ...] = ("train",)
    top_k: int = Field(default=5, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    per_collection_top_k: int = Field(default=5, ge=1)
    retrieval_token_budget: int = Field(default=12000, ge=1)
    fusion_strategy: Literal["rrf"] = "rrf"
    tokenizer_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    tokenizer_revision: str = "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    total_context_tokens: int = Field(default=32768, ge=1)
    reserved_output_tokens: int = Field(default=2048, ge=1)
    safety_margin_tokens: int = Field(default=256, ge=0)
    ollama_num_ctx: int | None = Field(default=None, ge=1)
    enforce_retrieval_token_budget: bool | None = None
    task_filter_enabled: bool | None = None
    max_retrieved_document_tokens: int | None = Field(default=None, ge=1)
    fail_on_prompt_budget_exceeded: bool | None = None
    structured_retries: int = Field(default=2, ge=0)
    structured_output_enabled: Literal[True] = True
    structured_output_format: Literal["json_schema"] = "json_schema"
    structured_output_schema_version: str = "task-specific-pydantic-v1"
    generation_max_tokens: int = Field(default=4096, ge=1)
    runtime_environment: Literal["wsl"] = "wsl"
    ollama_base_url: str = "http://localhost:11434"
    generation_provider: Literal["ollama"] = "ollama"
    generation_model: str = "qwen2.5-coder:7b"
    generation_model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_temperature: float = Field(default=0.0, ge=0.0)
    generation_top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    embedding_provider: Literal["ollama"] = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dimension: int = Field(default=1024, ge=1)
    embedding_model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_normalized: bool = True
    prompt_template_version: str = "canonical-se-prompt-v2"
    testing_prompt_template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    refactoring_prompt_template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    smoke_dataset_manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    smoke_dataset_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    collection_manifests: dict[str, FrozenCollectionIdentity]
    random_seed: int = 42
    retrieval_dataset_manifest_ids: tuple[str, ...] = ()
    require_runtime_assets: bool = True

    @model_validator(mode="after")
    def validate_controlled_matrix(self) -> SmokeExperimentConfig:
        if self.modes != SMOKE_MODES:
            raise ValueError("Default smoke config must declare no_rag, single RAG and MultiRAG.")
        if len(set(self.multi_collections)) != len(self.multi_collections):
            raise ValueError("MultiRAG collections must be unique.")
        if set(self.multi_collections) != {"testing_db", "refactoring_db"}:
            raise ValueError("Smoke MultiRAG must use testing_db and refactoring_db.")
        if self.single_collection != "mixed":
            raise ValueError("Smoke Single RAG must use the mixed collection.")
        if self.experiment_name != self.baseline_id:
            raise ValueError("experiment_name and baseline_id must identify the same baseline.")
        if set(self.collection_manifests) != {
            "mixed",
            "testing_db",
            "refactoring_db",
        }:
            raise ValueError("Frozen collection identities must cover all three baseline indexes.")
        if self.generation_max_tokens > self.total_context_tokens:
            raise ValueError("generation_max_tokens cannot exceed the context window.")
        if self.ollama_num_ctx is not None and self.total_context_tokens > self.ollama_num_ctx:
            raise ValueError("total_context_tokens cannot exceed ollama_num_ctx.")
        if self.fail_on_prompt_budget_exceeded and self.ollama_num_ctx is None:
            raise ValueError("fail_on_prompt_budget_exceeded requires an explicit ollama_num_ctx.")
        frozen_dataset_ids = {
            manifest_id
            for identity in self.collection_manifests.values()
            for manifest_id in identity.dataset_manifest_ids
        }
        if frozen_dataset_ids != set(self.retrieval_dataset_manifest_ids):
            raise ValueError(
                "retrieval_dataset_manifest_ids must match the frozen collection sources."
            )
        return self

    @property
    def default_planned_runs(self) -> int:
        return 24 * len(self.modes)


class SmokeSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    tasks: tuple[Literal["testing", "refactoring"], ...] = ()
    difficulties: tuple[Literal["easy", "medium", "tricky"], ...] = ()
    modes: tuple[RetrievalMode, ...] = ()
    case_ids: tuple[str, ...] = ()
    retry_failed: bool = False
    force: bool = False


class SmokeRunRecord(BaseModel):
    baseline_id: str = "legacy_unversioned"
    baseline_fingerprint: str = ""
    run_id: str
    case_id: str
    task: Literal["testing", "refactoring"]
    difficulty: Literal["easy", "medium", "tricky"]
    mode: RetrievalMode
    status: Literal["success", "failed"]
    attempt: int = Field(ge=1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = Field(default=0.0, ge=0.0)
    experiment_record: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


class SmokeRunResult(BaseModel):
    preflight_passed: bool
    fairness_passed: bool
    baseline_fingerprint: str
    baseline_fingerprint_matched: bool
    planned_runs: int
    executed_runs: int = 0
    skipped_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    output_dir: Path


def load_smoke_experiment_config(path: str | Path) -> SmokeExperimentConfig:
    return SmokeExperimentConfig.model_validate(read_yaml(path))
