from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from llm_ontology.retrieval.models import RetrievalTrace


class ExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: uuid4().hex)
    configuration: dict[str, Any]
    dataset_version: str
    embedding_model: str
    embedding_version: str
    llm_model: str
    llm_version: str
    retrieval_parameters: dict[str, Any]
    random_seed: int
    input: dict[str, Any]
    retrieval_trace: RetrievalTrace
    response: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    requested_task: str = ""
    canonical_task: str = ""
    retrieval_mode: str = ""
    collection: str | None = None
    dataset_manifest_ids: list[str] = Field(default_factory=list)
    embedding_remote_code_revision: str | None = None
    llm_digest: str | None = None
    prompt_artifact_path: str | None = None
    prompt_hash: str | None = None
    token_budget: dict[str, Any] = Field(default_factory=dict)
    structured_output_attempts: list[dict[str, Any]] = Field(default_factory=list)


class JsonlExperimentWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: ExperimentRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def read_all(self) -> list[ExperimentRecord]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return [ExperimentRecord.model_validate(json.loads(line)) for line in handle if line.strip()]
