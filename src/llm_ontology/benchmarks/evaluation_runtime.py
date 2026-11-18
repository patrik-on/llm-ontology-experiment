"""Local model/JDK runtime shared by the evaluation matrices."""
from __future__ import annotations
from pathlib import Path
import platform
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from llm_ontology.core.config import read_yaml

class EvaluationRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal["java_evaluation_runtime_v1"] = "java_evaluation_runtime_v1"
    java_home: Path
    work_root: Path
    junit_jar: Path
    junit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    training_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/train.jsonl")], min_length=1)
    validation_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/val.jsonl")], min_length=1)
    checkpoint_selection_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/val.jsonl")], min_length=1)
    retrieval_config: Path = Path("configs/retrieval/ollama_bge_m3_v3.yaml")
    hf_models_config: Path = Path("configs/evaluation/eval_models_v2_only.yaml")
    hf_model_name: str = Field(default="b2_testing_v2", min_length=1, max_length=100)
    generation_model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_new_tokens: int = Field(default=4096, ge=1, le=8192)
    generation_timeout_seconds: int = Field(default=1800, ge=1, le=7200)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    repeats: int = Field(default=2, ge=2, le=3)
    random_seed: Literal[42] = 42
    prompt_profile: Literal["testing-full-class-v2"] | None = None

def load_config(path: Path) -> EvaluationRuntime:
    raw = read_yaml(path)
    for key in ("java_home", "work_root", "junit_jar"):
        raw[key] = Path(raw[key]).expanduser().resolve()
    return EvaluationRuntime.model_validate(raw)

def require_wsl() -> None:
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise RuntimeError("This protocol runs only inside WSL/Linux, using .venv_wsl.")
