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


class SmokeExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    experiment_name: str = "baseline_v1"
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
    tokenizer_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    tokenizer_revision: str = "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    total_context_tokens: int = Field(default=32768, ge=1)
    reserved_output_tokens: int = Field(default=2048, ge=1)
    safety_margin_tokens: int = Field(default=256, ge=0)
    structured_retries: int = Field(default=2, ge=0)
    generation_max_tokens: int = Field(default=4096, ge=1)
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
    planned_runs: int
    executed_runs: int = 0
    skipped_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    output_dir: Path


def load_smoke_experiment_config(path: str | Path) -> SmokeExperimentConfig:
    return SmokeExperimentConfig.model_validate(read_yaml(path))
