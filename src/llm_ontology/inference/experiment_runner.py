from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field, model_validator

from llm_ontology.approaches import ApproachPromptBuilder, RetrievedContext
from llm_ontology.core.config import read_yaml
from llm_ontology.core.task_mode import CanonicalTask, resolve_task
from llm_ontology.evaluation.experiment_log import ExperimentRecord, JsonlExperimentWriter
from llm_ontology.inference.structured_output import StructuredOutputGenerator
from llm_ontology.providers.contracts import LLMProvider
from llm_ontology.retrieval.contracts import Retriever
from llm_ontology.retrieval.models import RetrievalMode, RetrievalRequest
from llm_ontology.retrieval.query import build_retrieval_query
from llm_ontology.retrieval.token_budget import ContextBudgeter, TokenCounter


ALLOWED_EXPERIMENT_CELLS: dict[CanonicalTask, set[str | None]] = {
    CanonicalTask.REFACTORING: {None, "refactor", "refactoring_db", "mixed"},
    CanonicalTask.TESTING: {None, "tests", "testing_db", "mixed"},
}
MULTIRAG_COLLECTIONS = {"testing_db", "refactoring_db", "literature_db"}


class RagExperimentConfig(BaseModel):
    enabled: bool = False
    baseline_id: str | None = None
    baseline_fingerprint: str | None = None
    requested_task: str
    canonical_task: CanonicalTask | None = None
    retrieval_mode: RetrievalMode
    collection: str | None = None
    collections: list[str] = Field(default_factory=list)
    dataset_version: str
    dataset_manifest_ids: list[str] = Field(default_factory=list)
    embedding_model: str
    embedding_revision: str
    embedding_remote_code_revision: str | None = None
    llm_model: str
    llm_version: str = "runtime_digest"
    generation_provider: str = "ollama"
    generation_max_tokens: int = Field(default=2048, ge=1)
    top_k: int = Field(default=5, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    per_collection_top_k: int = Field(default=5, ge=1, le=100)
    retrieval_query_strategy: str = "raw_input"
    retrieval_reranking_strategy: str = "none"
    retrieval_candidate_pool_size: int | None = Field(default=None, ge=1, le=100)
    allowed_splits: list[str] = Field(default_factory=lambda: ["train"])
    tokenizer_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    tokenizer_revision: str = "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    token_counting_method: str = "huggingface_tokenizer"
    total_context_tokens: int = Field(default=32768, ge=1)
    reserved_output_tokens: int = Field(default=2048, ge=1)
    safety_margin_tokens: int = Field(default=256, ge=0)
    retrieval_token_budget: int | None = Field(default=None, ge=1)
    max_retrieved_document_tokens: int | None = Field(default=None, ge=1)
    metadata_filter: dict[str, Any] = Field(default_factory=dict)
    runtime_context_tokens: int | None = Field(default=None, ge=1)
    fail_on_prompt_budget_exceeded: bool = False
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
            RetrievalMode.MULTI_COLLECTION_RAG,
        }:
            raise ValueError(
                "The baseline runner supports no_rag, single_collection_rag and "
                "multi_collection_rag; metadata RAG and ontology RAG are not selected."
            )
        if self.retrieval_mode == RetrievalMode.NO_RAG and self.collection is not None:
            raise ValueError("no_rag must not specify a collection.")
        if self.retrieval_mode == RetrievalMode.SINGLE_COLLECTION_RAG and self.collection is None:
            raise ValueError("single_collection_rag requires one collection.")
        if self.retrieval_mode == RetrievalMode.MULTI_COLLECTION_RAG:
            if self.collection is not None:
                raise ValueError("multi_collection_rag must use collections, not collection.")
            if len(self.collections) < 2 or not {"testing_db", "refactoring_db"}.issubset(
                self.collections
            ):
                raise ValueError("multi_collection_rag requires testing_db and refactoring_db.")
            unknown = set(self.collections) - MULTIRAG_COLLECTIONS
            if unknown:
                raise ValueError(f"Unsupported MultiRAG collections: {sorted(unknown)}")
        elif self.collections:
            raise ValueError("collections is reserved for multi_collection_rag.")
        if (
            self.retrieval_mode != RetrievalMode.MULTI_COLLECTION_RAG
            and self.collection not in ALLOWED_EXPERIMENT_CELLS[resolved.canonical]
        ):
            raise ValueError(
                f"Collection {self.collection!r} is not a controlled cell for "
                f"task {resolved.canonical.value!r}."
            )
        if (
            self.runtime_context_tokens is not None
            and self.total_context_tokens > self.runtime_context_tokens
        ):
            raise ValueError(
                "total_context_tokens cannot exceed the configured runtime context window."
            )
        if self.fail_on_prompt_budget_exceeded and self.runtime_context_tokens is None:
            raise ValueError("fail_on_prompt_budget_exceeded requires runtime_context_tokens.")
        if self.retrieval_query_strategy not in {"raw_input", "task_aware_v1"}:
            raise ValueError(
                f"Unsupported retrieval query strategy: {self.retrieval_query_strategy!r}"
            )
        if self.retrieval_reranking_strategy not in {"none", "code_aware_v1"}:
            raise ValueError(
                "Unsupported retrieval reranking strategy: "
                f"{self.retrieval_reranking_strategy!r}"
            )
        if (
            self.retrieval_candidate_pool_size is not None
            and self.retrieval_candidate_pool_size < self.top_k
        ):
            raise ValueError("retrieval_candidate_pool_size cannot be smaller than top_k.")
        if self.retrieval_reranking_strategy != "none" and (
            self.retrieval_candidate_pool_size is None
            or self.retrieval_candidate_pool_size <= self.top_k
        ):
            raise ValueError(
                "Retrieval reranking requires a candidate pool larger than top_k."
            )
        return self


class ExperimentCase(BaseModel):
    case_id: str
    instruction: str
    input_text: str
    requirements: str = ""
    project_context: str = ""
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
        retrieval_token_budget: int | None = None,
        max_retrieved_document_tokens: int | None = None,
        runtime_context_tokens: int | None = None,
        fail_on_prompt_budget_exceeded: bool = False,
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
            retrieval_token_budget=retrieval_token_budget,
            max_document_tokens=max_retrieved_document_tokens,
        )
        self.runtime_context_tokens = runtime_context_tokens
        self.fail_on_prompt_budget_exceeded = fail_on_prompt_budget_exceeded
        self.structured_generator = StructuredOutputGenerator(
            llm_provider, max_retries=structured_retries
        )

    def run_case(
        self,
        config: RagExperimentConfig,
        case: ExperimentCase,
        *,
        write_record: bool = True,
    ) -> ExperimentRecord:
        started = perf_counter()
        assert config.canonical_task is not None
        if not config.enabled:
            raise RuntimeError(
                "Experiment config is disabled. Attach approved dataset manifests before enabling it."
            )
        self._validate_runtime(config)
        retrieval_query = build_retrieval_query(
            strategy=config.retrieval_query_strategy,
            task=config.canonical_task.value,
            input_text=case.input_text,
            requirements=case.requirements,
            structured_identity=case.structured_identity,
        )
        retrieval = self.retriever.retrieve(
            RetrievalRequest(
                query=retrieval_query,
                mode=config.retrieval_mode,
                collections=(
                    config.collections
                    if config.retrieval_mode == RetrievalMode.MULTI_COLLECTION_RAG
                    else []
                    if config.collection is None
                    else [config.collection]
                ),
                allowed_splits=config.allowed_splits,
                metadata_filter=config.metadata_filter,
                top_k=config.top_k,
                max_context_tokens=(
                    config.retrieval_token_budget
                    or self.budgeter.retrieval_token_budget
                    or self.budgeter.total_context_tokens
                ),
                rrf_k=config.rrf_k,
                per_collection_top_k=config.per_collection_top_k,
                candidate_pool_size=config.retrieval_candidate_pool_size,
                reranking_strategy=config.retrieval_reranking_strategy,
            )
        )
        fixed_prompt = self.prompt_builder.build(
            task=config.canonical_task.value,
            instruction=case.instruction,
            input_text=case.input_text,
            requirements=case.requirements,
            project_context=case.project_context,
            approach="direct",
        ).text
        selection = self.budgeter.select(fixed_prompt, retrieval.documents)
        contexts = tuple(
            RetrievedContext(
                document_id=document.document_id,
                content=document.content,
                source=str(document.metadata.get("source", document.collection)),
                score=(
                    document.reranking_score
                    if document.reranking_score is not None
                    else document.score
                ),
                metadata={**document.metadata, "collection": document.collection},
            )
            for document in selection.documents
        )
        approach = {
            RetrievalMode.NO_RAG: "direct",
            RetrievalMode.SINGLE_COLLECTION_RAG: "rag",
            RetrievalMode.MULTI_COLLECTION_RAG: "multi_rag",
        }[config.retrieval_mode]
        if approach != "direct" and not contexts:
            raise RuntimeError("Token budget removed every retrieved document from a RAG prompt.")
        prepared = self.prompt_builder.build(
            task=config.canonical_task.value,
            instruction=case.instruction,
            input_text=case.input_text,
            contexts=contexts,
            approach=approach,
            requirements=case.requirements,
            project_context=case.project_context,
        )
        final_prompt_tokens = self.token_counter.count(prepared.text)
        runtime_context_tokens = config.runtime_context_tokens or self.runtime_context_tokens
        required_context_tokens = (
            final_prompt_tokens
            + self.budgeter.reserved_output_tokens
            + self.budgeter.safety_margin_tokens
        )
        prompt_budget_exceeded = (
            runtime_context_tokens is not None and required_context_tokens > runtime_context_tokens
        )
        if (
            config.fail_on_prompt_budget_exceeded or self.fail_on_prompt_budget_exceeded
        ) and prompt_budget_exceeded:
            raise RuntimeError(
                "Final prompt exceeds the configured Ollama context window: "
                f"prompt={final_prompt_tokens}, output_reserve="
                f"{self.budgeter.reserved_output_tokens}, safety_margin="
                f"{self.budgeter.safety_margin_tokens}, runtime_context="
                f"{runtime_context_tokens}."
            )
        prompt_path, prompt_hash = _write_prompt_artifact(
            config.prompt_artifacts_dir, case.case_id, prepared.text
        )
        digest = _resolve_digest(self.llm_provider)
        structured = self.structured_generator.generate(prepared.text, config.canonical_task)
        runtime_prompt_eval_count = _runtime_prompt_eval_count(structured.attempts)
        runtime_prompt_truncation_suspected = (
            runtime_prompt_eval_count is not None
            and final_prompt_tokens > 0
            and runtime_prompt_eval_count < final_prompt_tokens * 0.9
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
                "collections": config.collections,
                "top_k": config.top_k,
                "rrf_k": config.rrf_k,
                "per_collection_top_k": config.per_collection_top_k,
                "allowed_splits": config.allowed_splits,
                "metadata_filter": config.metadata_filter,
                "retrieval_token_budget": config.retrieval_token_budget,
                "max_retrieved_document_tokens": (config.max_retrieved_document_tokens),
            },
            random_seed=config.random_seed,
            input={
                "case_id": case.case_id,
                "input_text": case.input_text,
                "input_code_hash": hashlib.sha256(case.input_text.encode("utf-8")).hexdigest(),
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
            generation_provider=str(
                getattr(self.llm_provider, "provider_name", config.generation_provider)
            ),
            generation_model=config.llm_model,
            generation_model_digest=digest,
            prompt_artifact_path=str(prompt_path),
            prompt_hash=prompt_hash,
            prompt_template_version=prepared.prompt_template_version,
            prompt_template_sha256=prepared.prompt_template_sha256,
            normalized_prompt_sha256=prepared.normalized_prompt_sha256,
            full_prompt_sha256=prepared.full_prompt_sha256,
            token_budget={
                **selection.model_dump(mode="json", exclude={"documents"}),
                "final_prompt_tokens": final_prompt_tokens,
                "required_context_tokens": required_context_tokens,
                "runtime_context_tokens": runtime_context_tokens,
                "prompt_budget_exceeded": prompt_budget_exceeded,
                "runtime_prompt_eval_count": runtime_prompt_eval_count,
                "runtime_prompt_truncation_suspected": (runtime_prompt_truncation_suspected),
            },
            structured_output_attempts=[
                attempt.model_dump(mode="json") for attempt in structured.attempts
            ],
        )
        if write_record:
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
            "retrieval_token_budget": self.budgeter.retrieval_token_budget,
            "max_retrieved_document_tokens": self.budgeter.max_document_tokens,
            "runtime_context_tokens": self.runtime_context_tokens,
            "fail_on_prompt_budget_exceeded": self.fail_on_prompt_budget_exceeded,
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
    safe_case_id = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in case_id
    )
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


def _runtime_prompt_eval_count(attempts: list[Any]) -> int | None:
    if not attempts:
        return None
    value = attempts[0].generation_metadata.get("prompt_eval_count")
    return int(value) if isinstance(value, (int, float)) else None


def load_experiment_config(path: str | Path) -> RagExperimentConfig:
    return RagExperimentConfig.model_validate(read_yaml(path))
