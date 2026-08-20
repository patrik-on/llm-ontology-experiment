from __future__ import annotations

import json
import logging
import platform
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from llm_ontology.core.config import read_yaml
from llm_ontology.core.paths import resolve_path
from llm_ontology.evaluation.experiment_log import ExperimentRecord
from llm_ontology.inference.experiment_runner import (
    ExperimentCase,
    RagExperimentRunner,
    load_experiment_config,
)
from llm_ontology.retrieval.config import RagConfig, load_rag_config
from llm_ontology.retrieval.factory import (
    create_llm_provider,
    create_vector_store,
)
from llm_ontology.retrieval.models import RetrievalMode
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import CharacterTokenCounter
from llm_ontology.ui.logging import capture_run_logs
from llm_ontology.ui.models import (
    CollectionStatus,
    EnvironmentStatus,
    GeneratedOutputView,
    MetricsView,
    PromptView,
    RetrievalDocumentView,
    UIRunRequest,
    UIRunView,
    mode_from_label,
    task_from_label,
)
from llm_ontology.vectorstore.chroma import create_chroma_client
from llm_ontology.vectorstore.manifest import (
    CollectionManifestStore,
    IncompatibleCollectionError,
)

LOGGER = logging.getLogger("llm_ontology.ui")


class UISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=7860, ge=1, le=65535)
    default_task: str = "testing"
    default_mode: RetrievalMode = RetrievalMode.NO_RAG
    log_level: str = "INFO"
    retrieval_config: Path
    experiment_configs: dict[str, dict[str, Path]]
    history_path: Path = Path("experiments/results/ui/interactive_runs.jsonl")
    prompt_artifacts_dir: Path = Path("artifacts/prompts/ui")
    max_input_chars: int = Field(default=100_000, ge=1)
    structured_retries: int = Field(default=2, ge=0, le=10)
    environment_timeout_seconds: float = Field(default=3.0, gt=0.0, le=30.0)
    default_instructions: dict[str, str]

    @field_validator("default_task")
    @classmethod
    def supported_task(cls, value: str) -> str:
        if value not in {"testing", "refactoring"}:
            raise ValueError("UI default_task must be testing or refactoring.")
        return value

    @field_validator("log_level")
    @classmethod
    def supported_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"INFO", "DEBUG"}:
            raise ValueError("UI log_level must be INFO or DEBUG.")
        return value


def load_ui_settings(path: str | Path) -> UISettings:
    payload = read_yaml(path)
    if "ui" not in payload:
        raise ValueError("UI configuration must contain a top-level 'ui' section.")
    return UISettings.model_validate(payload["ui"])


class InteractiveRunner(Protocol):
    model_name: str

    def collection_for(self, task: str, mode: RetrievalMode) -> str | None: ...

    def run(self, request: UIRunRequest) -> ExperimentRecord: ...


class ConfiguredInteractiveRunner:
    """Thin adapter from an interactive request to the shared experiment runner."""

    def __init__(self, settings: UISettings, rag_config: RagConfig) -> None:
        self.settings = settings
        self.rag_config = rag_config
        self.model_name = rag_config.llm.model
        self.llm_provider = create_llm_provider(rag_config.llm)
        self._no_rag_retriever = VectorRetriever(_NoOpVectorStore())
        self._rag_retriever: VectorRetriever | None = None
        self.token_counter = CharacterTokenCounter()

    def collection_for(self, task: str, mode: RetrievalMode) -> str | None:
        if mode == RetrievalMode.NO_RAG:
            return None
        if mode == RetrievalMode.MULTI_COLLECTION_RAG:
            raise NotImplementedError("MultiRAG is not available yet.")
        config = self._base_config(task, mode)
        return config.collection

    def run(self, request: UIRunRequest) -> ExperimentRecord:
        if request.mode == RetrievalMode.MULTI_COLLECTION_RAG:
            raise NotImplementedError(
                "MultiRAG is not available because multi-collection retrieval and fusion "
                "are not implemented in the shared runner."
            )
        config = self._base_config(request.task, request.mode)
        config = config.model_copy(
            update={
                "enabled": True,
                "top_k": request.top_k,
                "results_path": resolve_path(self.settings.history_path),
                "prompt_artifacts_dir": resolve_path(self.settings.prompt_artifacts_dir),
                "tokenizer_model": self.token_counter.model_identifier,
                "tokenizer_revision": self.token_counter.model_revision,
                "token_counting_method": self.token_counter.method,
            }
        )
        instruction = request.requirements or self.settings.default_instructions[request.task]
        runner = RagExperimentRunner(
            retriever=self._retriever_for(request.mode),
            llm_provider=self.llm_provider,
            token_counter=self.token_counter,
            total_context_tokens=config.total_context_tokens,
            reserved_output_tokens=config.reserved_output_tokens,
            safety_margin_tokens=config.safety_margin_tokens,
            structured_retries=self.settings.structured_retries,
        )
        return runner.run_case(
            config,
            ExperimentCase(
                case_id=f"ui:{uuid4().hex}",
                instruction=instruction,
                input_text=request.source_code,
                metadata={"origin": "interactive_ui"},
            ),
        )

    def _retriever_for(self, mode: RetrievalMode) -> VectorRetriever:
        if mode == RetrievalMode.NO_RAG:
            return self._no_rag_retriever
        chroma_path = resolve_path(self.rag_config.vector_store.persist_path)
        if not chroma_path.exists():
            raise FileNotFoundError(f"Chroma database is missing: {chroma_path}")
        if self._rag_retriever is None:
            self._rag_retriever = VectorRetriever(create_vector_store(self.rag_config))
        return self._rag_retriever

    def _base_config(self, task: str, mode: RetrievalMode):
        try:
            path = self.settings.experiment_configs[task][mode.value]
        except KeyError as exc:
            raise ValueError(
                f"No UI experiment configuration for task={task!r}, mode={mode.value!r}."
            ) from exc
        return load_experiment_config(resolve_path(path))


class EnvironmentStatusService:
    def __init__(
        self,
        rag_config: RagConfig,
        *,
        timeout_seconds: float = 3.0,
        llm_provider_factory: Callable[[Any], Any] = create_llm_provider,
        chroma_client_factory: Callable[[str | Path | None], Any] = create_chroma_client,
    ) -> None:
        self.rag_config = rag_config
        self.timeout_seconds = timeout_seconds
        self.llm_provider_factory = llm_provider_factory
        self.chroma_client_factory = chroma_client_factory

    def inspect(self) -> EnvironmentStatus:
        errors: list[str] = []
        model_available = False
        model_digest = "N/A"
        ollama_status = "unavailable"
        try:
            llm_settings = self.rag_config.llm.model_copy(
                update={"timeout_seconds": self.timeout_seconds}
            )
            provider = self.llm_provider_factory(llm_settings)
            resolver = getattr(provider, "resolve_model_digest", None)
            if callable(resolver):
                model_digest = str(resolver())
            else:
                model_digest = str(getattr(provider, "model_version", "N/A"))
            model_available = True
            ollama_status = "available"
        except Exception as exc:  # noqa: BLE001 - status probes are best-effort.
            errors.append(_friendly_error(exc))

        chroma_path = resolve_path(self.rag_config.vector_store.persist_path)
        collections: list[CollectionStatus] = []
        chroma_status = "missing"
        if chroma_path.exists():
            try:
                client = self.chroma_client_factory(chroma_path)
                manifest_store = CollectionManifestStore(chroma_path)
                names = sorted(
                    getattr(collection, "name", str(collection))
                    for collection in client.list_collections()
                )
                for name in names:
                    collection = client.get_collection(name=name)
                    try:
                        manifest = manifest_store.read(name)
                    except IncompatibleCollectionError:
                        manifest = None
                    collections.append(
                        CollectionStatus(
                            name=name,
                            document_count=collection.count(),
                            embedding_model=(
                                manifest.embedding_model if manifest else "N/A"
                            ),
                            embedding_revision=(
                                manifest.embedding_revision or "N/A"
                                if manifest
                                else "N/A"
                            ),
                            chunker_version=(
                                manifest.chunker_version if manifest else "N/A"
                            ),
                            manifest_status="valid" if manifest else "missing",
                        )
                    )
                chroma_status = "available"
            except Exception as exc:  # noqa: BLE001 - status probes are best-effort.
                chroma_status = "error"
                errors.append(_friendly_error(exc))

        return EnvironmentStatus(
            ollama_status=ollama_status,
            configured_model=self.rag_config.llm.model,
            model_available=model_available,
            model_digest=model_digest,
            chroma_path=str(chroma_path),
            chroma_status=chroma_status,
            embedding_model=self.rag_config.embeddings.model,
            embedding_revision=self.rag_config.embeddings.revision or "N/A",
            python_version=platform.python_version(),
            collections=collections,
            errors=errors,
        )


class UIService:
    def __init__(
        self,
        settings: UISettings,
        runner: InteractiveRunner,
        environment_service: EnvironmentStatusService,
    ) -> None:
        self.settings = settings
        self.runner = runner
        self.environment_service = environment_service

    @property
    def model_name(self) -> str:
        return self.runner.model_name

    def collection_for_label(self, task_label: str, mode_label: str) -> str:
        try:
            collection = self.runner.collection_for(
                task_from_label(task_label), mode_from_label(mode_label)
            )
        except (ValueError, NotImplementedError):
            return "N/A"
        return collection or "Retrieval disabled"

    def run(
        self,
        *,
        task_label: str,
        mode_label: str,
        source_code: str,
        requirements: str,
        top_k: int,
        log_level: str,
    ) -> UIRunView:
        capture_id = uuid4().hex
        view: UIRunView
        with capture_run_logs(capture_id, level=log_level) as handler:
            try:
                request = UIRunRequest(
                    task=task_from_label(task_label),
                    mode=mode_from_label(mode_label),
                    source_code=source_code,
                    requirements=requirements,
                    top_k=top_k,
                    log_level=log_level,
                )
                if len(request.source_code) > self.settings.max_input_chars:
                    raise ValueError(
                        f"Java input exceeds the configured limit of "
                        f"{self.settings.max_input_chars} characters."
                    )
                LOGGER.info("Starting interactive run")
                LOGGER.info("Task: %s", request.task)
                LOGGER.info("Mode: %s", request.mode.value)
                collection = self.runner.collection_for(request.task, request.mode)
                LOGGER.info("Collection: %s", collection or "disabled")
                LOGGER.info("Calling configured model: %s", self.runner.model_name)
                record = self.runner.run(request)
                view = _record_to_view(record)
                LOGGER.info("Generation completed")
                LOGGER.info("Structured output valid")
                LOGGER.info("Run ID: %s", record.experiment_id)
            except Exception as exc:
                message = _friendly_error(exc)
                if log_level.upper() == "DEBUG":
                    LOGGER.exception("Interactive run failed: %s", message)
                else:
                    LOGGER.error("Interactive run failed: %s", message)
                view = UIRunView(
                    success=False,
                    run_id=capture_id,
                    status="Run failed",
                    error=message,
                    retrieval_message=(
                        "MultiRAG is not available yet."
                        if isinstance(exc, NotImplementedError)
                        else "No retrieval result is available."
                    ),
                    metrics=MetricsView(
                        values={
                            "model": self.runner.model_name,
                            "task": task_label,
                            "mode": mode_label,
                            "status": "failed",
                        }
                    ),
                )
        return view.model_copy(update={"logs": handler.text()})

    def environment_status(self) -> EnvironmentStatus:
        return self.environment_service.inspect()


def create_ui_service(config_path: str | Path = "configs/ui/local.yaml") -> UIService:
    settings = load_ui_settings(resolve_path(config_path))
    rag_config = load_rag_config(resolve_path(settings.retrieval_config))
    runner = ConfiguredInteractiveRunner(settings, rag_config)
    environment_service = EnvironmentStatusService(
        rag_config, timeout_seconds=settings.environment_timeout_seconds
    )
    return UIService(settings, runner, environment_service)


class _NoOpVectorStore:
    def query(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise AssertionError("no_rag must never query the vector store")


def _record_to_view(record: ExperimentRecord) -> UIRunView:
    try:
        response = json.loads(record.response)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Structured output failed: stored response is not valid JSON.") from exc

    code_value = (
        response.get("generated_tests")
        if record.canonical_task == "testing"
        else response.get("refactored_code")
    )
    code = _strip_code_fence(str(code_value or ""))
    output = GeneratedOutputView(
        code=code,
        summary=str(response.get("analysis_summary", "")),
        detected_code_smells=list(response.get("detected_code_smells") or []),
        applied_refactorings=list(response.get("recommended_refactorings") or []),
        assumptions=list(response.get("assumptions") or []),
        warnings=list(response.get("warnings") or []),
        raw_response=response,
    )

    prompt_document_ids = set(record.retrieval_trace.prompt_document_ids)
    retrieval_documents = [
        _retrieval_document_view(rank, document, prompt_document_ids)
        for rank, document in enumerate(
            record.retrieval_trace.retrieved_documents, start=1
        )
    ]
    prompt_text = ""
    if record.prompt_artifact_path:
        path = Path(record.prompt_artifact_path)
        if path.is_file():
            prompt_text = path.read_text(encoding="utf-8")

    token_budget = record.token_budget
    prompt_estimate = _sum_optional_numbers(
        token_budget.get("fixed_prompt_tokens"),
        token_budget.get("retrieval_tokens"),
    )
    prompt = PromptView(
        final_prompt=prompt_text,
        prompt_hash=record.prompt_hash or "N/A",
        prompt_tokens=prompt_estimate if prompt_estimate is not None else "N/A",
        retrieval_tokens=token_budget.get("retrieval_tokens", "N/A"),
        counting_method=str(token_budget.get("counting_method", "N/A")),
        artifact_path=record.prompt_artifact_path or "N/A",
    )
    metrics = MetricsView(values=_metrics(record, prompt_estimate))
    retrieval_message = (
        "Retrieval disabled."
        if record.retrieval_mode == RetrievalMode.NO_RAG.value
        else f"Retrieved {len(retrieval_documents)} document(s); "
        f"{len(prompt_document_ids)} selected for the prompt."
    )
    return UIRunView(
        success=True,
        run_id=record.experiment_id,
        status="Run completed",
        output=output,
        retrieval_message=retrieval_message,
        retrieval_documents=retrieval_documents,
        prompt=prompt,
        metrics=metrics,
    )


def _retrieval_document_view(
    rank: int, document: Any, prompt_document_ids: set[str]
) -> RetrievalDocumentView:
    metadata = document.metadata
    preview = " ".join(document.content.split())
    if len(preview) > 500:
        preview = preview[:497].rstrip() + "..."
    return RetrievalDocumentView(
        rank=rank,
        document_id=document.document_id,
        collection=document.collection,
        source_type=str(metadata.get("document_type", "N/A")),
        dataset_name=str(metadata.get("dataset", "N/A")),
        score=(
            document.reranking_score
            if document.reranking_score is not None
            else document.score
        ),
        class_name=str(metadata.get("class_name", "N/A")),
        method_name=str(
            metadata.get("method_name", metadata.get("focal_method_name", "N/A"))
        ),
        source_path=str(metadata.get("source_uri", metadata.get("source", "N/A"))),
        used_in_prompt=document.document_id in prompt_document_ids,
        preview=preview,
        content=document.content,
    )


def _metrics(record: ExperimentRecord, prompt_estimate: int | None) -> dict[str, Any]:
    attempts = record.structured_output_attempts
    metadata = [attempt.get("generation_metadata") or {} for attempt in attempts]
    prompt_counts = [
        value
        for item in metadata
        if isinstance((value := item.get("prompt_eval_count")), (int, float))
    ]
    completion_counts = [
        value
        for item in metadata
        if isinstance((value := item.get("eval_count")), (int, float))
    ]
    generation_latencies = [
        value
        for item in metadata
        if isinstance((value := item.get("client_latency_ms")), (int, float))
    ]
    validation_failures = sum(bool(attempt.get("validation_errors")) for attempt in attempts)
    return {
        "model": record.llm_model,
        "model_digest": record.llm_digest or "N/A",
        "task": record.canonical_task,
        "mode": record.retrieval_mode,
        "collections": record.collection or "N/A",
        "prompt_tokens": int(sum(prompt_counts)) if prompt_counts else prompt_estimate or "N/A",
        "completion_tokens": (
            int(sum(completion_counts)) if completion_counts else "N/A"
        ),
        "retrieval_tokens": record.token_budget.get("retrieval_tokens", "N/A"),
        "retrieval_latency_ms": record.retrieval_trace.total_latency_ms,
        "generation_latency_ms": (
            round(float(sum(generation_latencies)), 3)
            if generation_latencies
            else "N/A"
        ),
        "total_latency_ms": round(record.duration_ms, 3),
        "format_retries": validation_failures,
        "repair_retries": max(0, len(attempts) - 1),
        "compile_success": record.metrics.get("compile_success", "N/A"),
        "tests_passed": record.metrics.get("tests_passed", "N/A"),
        "validation_status": record.metrics.get("validation_status", "N/A"),
        "run_id": record.experiment_id,
    }


def _sum_optional_numbers(*values: Any) -> int | None:
    if not all(isinstance(value, (int, float)) for value in values):
        return None
    return int(sum(values))


def _strip_code_fence(value: str) -> str:
    match = re.fullmatch(
        r"\s*```(?:java)?\s*(.*?)\s*```\s*",
        value,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else value.strip()


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, ValidationError):
        return "Invalid input: " + "; ".join(
            error["msg"] for error in exc.errors()
        )
    if isinstance(exc, IncompatibleCollectionError):
        return "Stale or missing collection manifest: " + text
    if isinstance(exc, NotImplementedError):
        return text
    if "not reachable" in lowered or "ollama server" in lowered:
        return "Ollama server unavailable. Start Ollama and refresh Environment status."
    if "not installed" in lowered and "ollama" in lowered:
        return "Configured Ollama model is not installed: " + text
    if "collection" in lowered and (
        "does not exist" in lowered or "not found" in lowered or "missing" in lowered
    ):
        return "Chroma collection is missing: " + text
    if "chroma database" in lowered and "missing" in lowered:
        return text
    if "chromadb is not installed" in lowered:
        return "ChromaDB is unavailable. Install the project rag dependencies."
    if "fixed prompt exceeds" in lowered or "context window" in lowered:
        return "Prompt is too large for the configured token budget."
    if "structured output" in lowered:
        return "Structured output failed: " + text
    if "java input" in lowered:
        return text
    if "configuration" in lowered or "config" in lowered:
        return "Configuration error: " + text
    return text or exc.__class__.__name__
