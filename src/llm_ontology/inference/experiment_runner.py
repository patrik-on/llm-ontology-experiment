from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field, model_validator

from llm_ontology.approaches import ApproachPromptBuilder, RetrievedContext
from llm_ontology.approaches.context_prompt import contextual_prompt
from llm_ontology.core.config import read_yaml
from llm_ontology.core.task_mode import CanonicalTask, resolve_task
from llm_ontology.evaluation.experiment_log import ExperimentRecord, JsonlExperimentWriter
from llm_ontology.inference.structured_output import StructuredOutputGenerator
from llm_ontology.providers.contracts import LLMProvider
from llm_ontology.retrieval.contracts import Retriever
from llm_ontology.retrieval.models import RetrievalMode, RetrievalRequest
from llm_ontology.retrieval.token_budget import ContextBudgeter, TokenCounter


ALLOWED_EXPERIMENT_CELLS: dict[CanonicalTask, set[str | None]] = {
    CanonicalTask.REFACTORING: {None, "refactor", "mixed"},
    CanonicalTask.TESTING: {None, "tests", "mixed"},
}


class RagExperimentConfig(BaseModel):
    enabled: bool = False
    requested_task: str
    canonical_task: CanonicalTask | None = None
    retrieval_mode: RetrievalMode
    collection: str | None = None
    dataset_version: str
    dataset_manifest_ids: list[str] = Field(default_factory=list)
    embedding_model: str
    embedding_revision: str
    embedding_remote_code_revision: str | None = None
    llm_model: str
    llm_version: str = "runtime_digest"
    top_k: int = Field(default=5, ge=1)
    allowed_splits: list[str] = Field(default_factory=lambda: ["train"])
    tokenizer_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    tokenizer_revision: str = "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    token_counting_method: str = "huggingface_tokenizer"
    total_context_tokens: int = Field(default=32768, ge=1)
    reserved_output_tokens: int = Field(default=2048, ge=1)
    safety_margin_tokens: int = Field(default=256, ge=0)
    random_seed: int = 42
    results_path: Path
    prompt_artifacts_dir: Path

    @model_validator(mode="after")
    def validate_experiment_cell(self) -> RagExperimentConfig:
        resolved = resolve_task(self.requested_task)
        self.requested_task = resolved.requested
        self.canonical_task = resolved.canonical
        if self.retrieval_mode not in {
            RetrievalMode.NO_RAG,
            RetrievalMode.SINGLE_COLLECTION_RAG,
        }:
            raise ValueError(
                "The baseline runner supports only no_rag and single_collection_rag; "
                "metadata RAG and MultiRAG are preserved but not selected automatically."
            )
        if self.retrieval_mode == RetrievalMode.NO_RAG and self.collection is not None:
            raise ValueError("no_rag must not specify a collection.")
        if self.retrieval_mode == RetrievalMode.SINGLE_COLLECTION_RAG and self.collection is None:
            raise ValueError("single_collection_rag requires one collection.")
        if self.collection not in ALLOWED_EXPERIMENT_CELLS[resolved.canonical]:
            raise ValueError(
                f"Collection {self.collection!r} is not a controlled cell for "
                f"task {resolved.canonical.value!r}."
            )
        return self


class ExperimentCase(BaseModel):
    case_id: str
    instruction: str
    input_text: str
    structured_identity: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagExperimentRunner:
    """Run one controlled matrix cell without implicitly enabling legacy RAG modes."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        llm_provider: LLMProvider,
        token_counter: TokenCounter,
        total_context_tokens: int,
        reserved_output_tokens: int,
        safety_margin_tokens: int = 256,
        structured_retries: int = 2,
        prompt_builder: ApproachPromptBuilder | None = None,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.token_counter = token_counter
        self.prompt_builder = prompt_builder or ApproachPromptBuilder()
        self.budgeter = ContextBudgeter(
            token_counter,
            total_context_tokens=total_context_tokens,
            reserved_output_tokens=reserved_output_tokens,
            safety_margin_tokens=safety_margin_tokens,
        )
        self.structured_generator = StructuredOutputGenerator(
            llm_provider, max_retries=structured_retries
        )

    def run_case(
        self,
        config: RagExperimentConfig,
        case: ExperimentCase,
    ) -> ExperimentRecord:
        started = perf_counter()
        assert config.canonical_task is not None
        if not config.enabled:
            raise RuntimeError(
                "Experiment config is disabled. Attach approved dataset manifests before enabling it."
            )
        self._validate_runtime(config)
        retrieval = self.retriever.retrieve(
            RetrievalRequest(
                query=case.input_text,
                mode=config.retrieval_mode,
                collections=[] if config.collection is None else [config.collection],
                allowed_splits=config.allowed_splits,
                top_k=config.top_k,
                max_context_tokens=self.budgeter.total_context_tokens,
            )
        )
        fixed_prompt = (
            self.prompt_builder.build(
                task=config.canonical_task.value,
                instruction=case.instruction,
                input_text=case.input_text,
                approach="direct",
            ).text
            if config.retrieval_mode == RetrievalMode.NO_RAG
            else contextual_prompt(case.instruction, case.input_text, "")
        )
        selection = self.budgeter.select(fixed_prompt, retrieval.documents)
        contexts = tuple(
            RetrievedContext(
                document_id=document.document_id,
                content=document.content,
                source=str(document.metadata.get("source", document.collection)),
                score=document.reranking_score or document.score,
                metadata={**document.metadata, "collection": document.collection},
            )
            for document in selection.documents
        )
        approach = "direct" if config.retrieval_mode == RetrievalMode.NO_RAG else "rag"
        if approach == "rag" and not contexts:
            raise RuntimeError("Token budget removed every retrieved document from a RAG prompt.")
        prepared = self.prompt_builder.build(
            task=config.canonical_task.value,
            instruction=case.instruction,
            input_text=case.input_text,
            contexts=contexts,
            approach=approach,
        )
        prompt_path, prompt_hash = _write_prompt_artifact(
            config.prompt_artifacts_dir, case.case_id, prepared.text
        )
        digest = _resolve_digest(self.llm_provider)
        structured = self.structured_generator.generate(
            prepared.text, config.canonical_task
        )
        retrieval.trace.prompt_document_ids = selection.selected_document_ids
        retrieval.trace.estimated_context_tokens = selection.retrieval_tokens
        record = ExperimentRecord(
            configuration=config.model_dump(mode="json"),
            dataset_version=config.dataset_version,
            embedding_model=config.embedding_model,
            embedding_version=config.embedding_revision,
            llm_model=config.llm_model,
            llm_version=config.llm_version,
            retrieval_parameters={
                "mode": config.retrieval_mode.value,
                "collection": config.collection,
                "top_k": config.top_k,
                "allowed_splits": config.allowed_splits,
            },
            random_seed=config.random_seed,
            input={
                "case_id": case.case_id,
                "input_text": case.input_text,
                "input_code_hash": hashlib.sha256(
                    case.input_text.encode("utf-8")
                ).hexdigest(),
                "structured_identity": case.structured_identity,
                "metadata": case.metadata,
            },
            retrieval_trace=retrieval.trace,
            response=structured.answer.model_dump_json(),
            duration_ms=(perf_counter() - started) * 1000,
            requested_task=config.requested_task,
            canonical_task=config.canonical_task.value,
            retrieval_mode=config.retrieval_mode.value,
            collection=config.collection,
            dataset_manifest_ids=config.dataset_manifest_ids,
            embedding_remote_code_revision=config.embedding_remote_code_revision,
            llm_digest=digest,
            prompt_artifact_path=str(prompt_path),
            prompt_hash=prompt_hash,
            token_budget=selection.model_dump(mode="json", exclude={"documents"}),
            structured_output_attempts=[
                attempt.model_dump(mode="json") for attempt in structured.attempts
            ],
        )
        JsonlExperimentWriter(config.results_path).append(record)
        return record

    def _validate_runtime(self, config: RagExperimentConfig) -> None:
        mismatches = []
        expected = {
            "tokenizer_model": self.token_counter.model_identifier,
            "tokenizer_revision": self.token_counter.model_revision,
            "token_counting_method": self.token_counter.method,
            "total_context_tokens": self.budgeter.total_context_tokens,
            "reserved_output_tokens": self.budgeter.reserved_output_tokens,
            "safety_margin_tokens": self.budgeter.safety_margin_tokens,
        }
        for field, runtime_value in expected.items():
            configured_value = getattr(config, field)
            if configured_value != runtime_value:
                mismatches.append(
                    f"{field}: config={configured_value!r}, runtime={runtime_value!r}"
                )
        if mismatches:
            raise ValueError("Runner/config reproducibility mismatch: " + "; ".join(mismatches))


def _write_prompt_artifact(root: Path, case_id: str, prompt: str) -> tuple[Path, str]:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    safe_case_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in case_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{safe_case_id}-{digest[:12]}.txt"
    temporary = path.with_suffix(".txt.tmp")
    temporary.write_text(prompt, encoding="utf-8")
    temporary.replace(path)
    return path, digest


def _resolve_digest(provider: LLMProvider) -> str | None:
    digest = getattr(provider, "model_digest", None)
    if digest:
        return str(digest)
    resolver = getattr(provider, "resolve_model_digest", None)
    if callable(resolver):
        return str(resolver())
    return None


def load_experiment_config(path: str | Path) -> RagExperimentConfig:
    return RagExperimentConfig.model_validate(read_yaml(path))
