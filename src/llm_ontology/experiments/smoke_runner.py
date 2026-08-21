from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from llm_ontology.benchmarks.smoke import SmokeCase, load_smoke_cases, load_smoke_manifest
from llm_ontology.evaluation.experiment_log import ExperimentRecord
from llm_ontology.evaluation.refactoring_metrics import compute_refactoring_metrics
from llm_ontology.evaluation.test_metrics import compute_testing_metrics
from llm_ontology.experiments.fairness import audit_prompt_fairness, smoke_project_context
from llm_ontology.experiments.baseline import (
    BaselineMismatchError,
    collection_content_hash,
    collection_manifest_id,
    require_matching_fingerprint,
    write_baseline_artifacts,
)
from llm_ontology.experiments.smoke_models import (
    FrozenCollectionIdentity,
    SmokeExperimentConfig,
    SmokeRunRecord,
    SmokeRunResult,
    SmokeSelection,
)
from llm_ontology.ingestion.manifest import DatasetManifest
from llm_ontology.experiments.smoke_reporting import (
    append_run_record,
    latest_run_records,
    read_run_history,
    write_smoke_reports,
)
from llm_ontology.inference.experiment_runner import (
    ExperimentCase,
    RagExperimentConfig,
    RagExperimentRunner,
)
from llm_ontology.inference.prompting import (
    PROMPT_TEMPLATE_VERSION,
    canonical_prompt_template,
)
from llm_ontology.inference.structured_output import STRUCTURED_OUTPUT_SCHEMA_VERSION
from llm_ontology.retrieval.config import RagConfig, load_rag_config
from llm_ontology.retrieval.factory import (
    create_embedding_provider,
    create_llm_provider,
    create_vector_store,
)
from llm_ontology.retrieval.models import RetrievalMode
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter
from llm_ontology.vectorstore.manifest import (
    CollectionManifest,
    CollectionManifestStore,
    IncompatibleCollectionError,
)


CaseExecutor = Callable[[RagExperimentConfig, ExperimentCase], ExperimentRecord]


class SmokeExperimentRunner:
    """Orchestrate smoke cases over the existing retrieval/inference/evaluation flow."""

    def __init__(
        self,
        config: SmokeExperimentConfig,
        *,
        case_executor: CaseExecutor | None = None,
    ) -> None:
        self.config = config
        self._case_executor = case_executor
        self._rag_config: RagConfig | None = None
        self._shared_runner: RagExperimentRunner | None = None

    def run(
        self,
        selection: SmokeSelection | None = None,
        *,
        dry_run: bool = False,
    ) -> SmokeRunResult:
        selected = selection or SmokeSelection()
        cases = load_smoke_cases(self.config.dataset_root)
        manifest = load_smoke_manifest(self.config.dataset_root)
        environment = self._preflight(cases, manifest)
        fairness = audit_prompt_fairness(cases)
        if not fairness["passed"]:
            write_smoke_reports(self.config, planned_runs=0, fairness_audit=fairness)
            raise RuntimeError("Canonical prompt fairness audit failed.")

        write_baseline_artifacts(self.config, self._load_rag_config(), environment)

        planned = self._select_matrix(cases, selected)
        write_smoke_reports(
            self.config,
            planned_runs=len(planned),
            fairness_audit=fairness,
        )
        if dry_run:
            return SmokeRunResult(
                preflight_passed=True,
                fairness_passed=True,
                baseline_fingerprint=self.config.baseline_fingerprint,
                baseline_fingerprint_matched=True,
                planned_runs=len(planned),
                output_dir=self.config.output_dir,
            )

        runs_path = self.config.output_dir / "runs.jsonl"
        latest = latest_run_records(
            read_run_history(runs_path),
            baseline_id=self.config.baseline_id,
            baseline_fingerprint=self.config.baseline_fingerprint,
        )
        executed = skipped = succeeded = failed = 0
        for case, mode in planned:
            run_id = _run_id(case.id, mode)
            previous = latest.get(run_id)
            if not self._should_execute(previous, selected):
                skipped += 1
                continue
            attempt = 1 if previous is None else previous.attempt + 1
            record = self._execute_one(case, mode, attempt, manifest.manifest_id)
            append_run_record(runs_path, record)
            latest[run_id] = record
            executed += 1
            if record.status == "success":
                succeeded += 1
            else:
                failed += 1

        write_smoke_reports(
            self.config,
            planned_runs=len(planned),
            fairness_audit=fairness,
        )
        return SmokeRunResult(
            preflight_passed=True,
            fairness_passed=True,
            baseline_fingerprint=self.config.baseline_fingerprint,
            baseline_fingerprint_matched=True,
            planned_runs=len(planned),
            executed_runs=executed,
            skipped_runs=skipped,
            successful_runs=succeeded,
            failed_runs=failed,
            output_dir=self.config.output_dir,
        )

    def _select_matrix(
        self,
        cases: list[SmokeCase],
        selection: SmokeSelection,
    ) -> list[tuple[SmokeCase, RetrievalMode]]:
        known_ids = {case.id for case in cases}
        unknown = sorted(set(selection.case_ids) - known_ids)
        if unknown:
            raise ValueError(f"Unknown smoke case IDs: {unknown}")
        selected_cases = [
            case
            for case in cases
            if (not selection.tasks or case.task in selection.tasks)
            and (not selection.difficulties or case.difficulty.value in selection.difficulties)
            and (not selection.case_ids or case.id in selection.case_ids)
        ]
        selected_modes = selection.modes or self.config.modes
        unsupported = set(selected_modes) - set(self.config.modes)
        if unsupported:
            raise ValueError(f"Modes are outside the smoke config: {sorted(unsupported)}")
        return [(case, mode) for case in selected_cases for mode in selected_modes]

    @staticmethod
    def _should_execute(
        previous: SmokeRunRecord | None,
        selection: SmokeSelection,
    ) -> bool:
        if selection.force:
            return True
        if previous is None:
            return not selection.retry_failed
        if previous.status == "success":
            return False
        return selection.retry_failed

    def _execute_one(
        self,
        case: SmokeCase,
        mode: RetrievalMode,
        attempt: int,
        smoke_manifest_id: str,
    ) -> SmokeRunRecord:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        try:
            experiment_config = self._experiment_config(case, mode, smoke_manifest_id)
            experiment_case = ExperimentCase(
                case_id=case.id,
                instruction="",
                input_text=case.input.source_code,
                requirements=case.input.requirements,
                project_context=smoke_project_context(case),
                structured_identity={
                    "class_name": case.input.class_name,
                    "focal_method": case.input.focal_method,
                    "input_code_hash": case.input_code_hash,
                },
                metadata={
                    "benchmark": "handcrafted_smoke_v1",
                    "difficulty": case.difficulty.value,
                    "title": case.title,
                    "allowed_for_indexing": False,
                },
            )
            experiment = self._execute_case(experiment_config, experiment_case)
            metrics = _evaluate(case, experiment)
            experiment = experiment.model_copy(update={"metrics": metrics})
            return SmokeRunRecord(
                baseline_id=self.config.baseline_id,
                baseline_fingerprint=self.config.baseline_fingerprint,
                run_id=_run_id(case.id, mode),
                case_id=case.id,
                task=case.task,
                difficulty=case.difficulty.value,
                mode=mode,
                status="success",
                attempt=attempt,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(perf_counter() - started) * 1000,
                experiment_record=experiment.model_dump(mode="json"),
                metrics=metrics,
            )
        except Exception as exc:  # one failed cell must not discard completed cells
            return SmokeRunRecord(
                baseline_id=self.config.baseline_id,
                baseline_fingerprint=self.config.baseline_fingerprint,
                run_id=_run_id(case.id, mode),
                case_id=case.id,
                task=case.task,
                difficulty=case.difficulty.value,
                mode=mode,
                status="failed",
                attempt=attempt,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    def _execute_case(
        self,
        config: RagExperimentConfig,
        case: ExperimentCase,
    ) -> ExperimentRecord:
        if self._case_executor is not None:
            return self._case_executor(config, case)
        if self._shared_runner is None:
            self._shared_runner = self._build_shared_runner()
        return self._shared_runner.run_case(config, case, write_record=False)

    def _build_shared_runner(self) -> RagExperimentRunner:
        rag = self._load_rag_config()
        counter = HuggingFaceTokenCounter(
            model_identifier=self.config.tokenizer_model,
            model_revision=self.config.tokenizer_revision,
        )
        return RagExperimentRunner(
            retriever=VectorRetriever(create_vector_store(rag)),
            llm_provider=create_llm_provider(
                rag.llm.model_copy(update={"max_tokens": self.config.generation_max_tokens})
            ),
            token_counter=counter,
            total_context_tokens=self.config.total_context_tokens,
            reserved_output_tokens=self.config.reserved_output_tokens,
            safety_margin_tokens=self.config.safety_margin_tokens,
            retrieval_token_budget=(
                self.config.retrieval_token_budget
                if self.config.enforce_retrieval_token_budget
                else None
            ),
            max_retrieved_document_tokens=(self.config.max_retrieved_document_tokens),
            runtime_context_tokens=self.config.ollama_num_ctx,
            fail_on_prompt_budget_exceeded=bool(self.config.fail_on_prompt_budget_exceeded),
            structured_retries=self.config.structured_retries,
        )

    def _experiment_config(
        self,
        case: SmokeCase,
        mode: RetrievalMode,
        smoke_manifest_id: str,
    ) -> RagExperimentConfig:
        rag = self._load_rag_config()
        is_single = mode == RetrievalMode.SINGLE_COLLECTION_RAG
        is_multi = mode == RetrievalMode.MULTI_COLLECTION_RAG
        return RagExperimentConfig(
            enabled=True,
            baseline_id=self.config.baseline_id,
            baseline_fingerprint=self.config.baseline_fingerprint,
            requested_task=case.task,
            retrieval_mode=mode,
            collection=self.config.single_collection if is_single else None,
            collections=list(self.config.multi_collections) if is_multi else [],
            dataset_version="handcrafted_smoke_v1@1.0",
            dataset_manifest_ids=[
                smoke_manifest_id,
                *self.config.retrieval_dataset_manifest_ids,
            ],
            embedding_model=rag.embeddings.model,
            embedding_revision=rag.embeddings.version,
            embedding_remote_code_revision=rag.embeddings.remote_code_revision,
            llm_model=rag.llm.model,
            llm_version=rag.llm.version,
            generation_provider=rag.llm.provider,
            generation_max_tokens=self.config.generation_max_tokens,
            top_k=self.config.top_k,
            rrf_k=self.config.rrf_k,
            per_collection_top_k=self.config.per_collection_top_k,
            retrieval_query_strategy=(
                self.config.retrieval_query_strategy or rag.retrieval.query_strategy
            ),
            retrieval_reranking_strategy=(
                self.config.retrieval_reranking_strategy
                or rag.retrieval.reranking_strategy
            ),
            retrieval_candidate_pool_size=(
                self.config.retrieval_candidate_pool_size
                or rag.retrieval.candidate_pool_size
            ),
            allowed_splits=list(self.config.allowed_splits),
            tokenizer_model=self.config.tokenizer_model,
            tokenizer_revision=self.config.tokenizer_revision,
            token_counting_method="huggingface_tokenizer",
            total_context_tokens=self.config.total_context_tokens,
            reserved_output_tokens=self.config.reserved_output_tokens,
            safety_margin_tokens=self.config.safety_margin_tokens,
            retrieval_token_budget=(
                self.config.retrieval_token_budget
                if self.config.enforce_retrieval_token_budget
                else None
            ),
            max_retrieved_document_tokens=(self.config.max_retrieved_document_tokens),
            metadata_filter=(
                {"task": case.task}
                if self.config.task_filter_enabled and mode != RetrievalMode.NO_RAG
                else {}
            ),
            runtime_context_tokens=self.config.ollama_num_ctx,
            fail_on_prompt_budget_exceeded=bool(self.config.fail_on_prompt_budget_exceeded),
            random_seed=self.config.random_seed,
            results_path=self.config.output_dir / "runs.jsonl",
            prompt_artifacts_dir=self.config.output_dir / "prompts" / case.id / mode.value,
        )

    def _preflight(
        self,
        cases: list[SmokeCase],
        manifest: DatasetManifest,
    ) -> dict[str, Any]:
        require_matching_fingerprint(self.config)
        if len(cases) != 24:
            raise ValueError(f"Smoke preflight expected 24 cases, found {len(cases)}.")
        rag = self._load_rag_config()
        mismatches: list[str] = []

        def check(name: str, actual: Any, expected: Any) -> None:
            if actual != expected:
                mismatches.append(f"{name}: expected={expected!r}, actual={actual!r}")

        check("runtime.environment", rag.runtime.environment, self.config.runtime_environment)
        check("runtime.status", rag.runtime.status, "current")
        check("runtime.ollama_base_url", rag.runtime.ollama_base_url, self.config.ollama_base_url)
        check("generation.provider", rag.llm.provider, self.config.generation_provider)
        check("generation.model", rag.llm.model, self.config.generation_model)
        check("generation.base_url", rag.llm.base_url, self.config.ollama_base_url)
        check("generation.temperature", rag.llm.temperature, self.config.generation_temperature)
        check("generation.top_p", rag.llm.top_p, self.config.generation_top_p)
        check("generation.seed", rag.llm.seed, self.config.random_seed)
        if self.config.ollama_num_ctx is not None:
            check(
                "generation.context_window_tokens",
                rag.llm.context_window_tokens,
                self.config.ollama_num_ctx,
            )
        check("embeddings.provider", rag.embeddings.provider, self.config.embedding_provider)
        check("embeddings.model", rag.embeddings.model, self.config.embedding_model)
        check("embeddings.dimension", rag.embeddings.dimension, self.config.embedding_dimension)
        check("embeddings.normalized", rag.embeddings.normalized, self.config.embedding_normalized)
        check("embeddings.base_url", rag.embeddings.base_url, self.config.ollama_base_url)
        check("retrieval.top_k", rag.retrieval.top_k, self.config.top_k)
        check(
            "retrieval.max_context_tokens",
            rag.retrieval.max_context_tokens,
            self.config.retrieval_token_budget,
        )
        check("retrieval.rrf_k", rag.retrieval.rrf_k, self.config.rrf_k)
        check(
            "retrieval.per_collection_top_k",
            rag.retrieval.per_collection_top_k,
            self.config.per_collection_top_k,
        )
        if self.config.retrieval_query_strategy is not None:
            check(
                "retrieval.query_strategy",
                rag.retrieval.query_strategy,
                self.config.retrieval_query_strategy,
            )
        if self.config.retrieval_reranking_strategy is not None:
            check(
                "retrieval.reranking_strategy",
                rag.retrieval.reranking_strategy,
                self.config.retrieval_reranking_strategy,
            )
        if self.config.retrieval_candidate_pool_size is not None:
            check(
                "retrieval.candidate_pool_size",
                rag.retrieval.candidate_pool_size,
                self.config.retrieval_candidate_pool_size,
            )
        check(
            "retrieval.allowed_splits",
            tuple(rag.retrieval.allowed_splits),
            self.config.allowed_splits,
        )
        check("retrieval.collections", tuple(rag.retrieval.collections), ("mixed",))
        check("retrieval.mode", rag.retrieval.mode.value, "single_collection_rag")
        check(
            "ingestion.allowed_splits",
            tuple(rag.ingestion.allowed_splits),
            self.config.allowed_splits,
        )
        check("prompt.version", PROMPT_TEMPLATE_VERSION, self.config.prompt_template_version)
        check(
            "structured_output.schema_version",
            STRUCTURED_OUTPUT_SCHEMA_VERSION,
            self.config.structured_output_schema_version,
        )
        check(
            "prompt.testing_sha256",
            _prompt_template_hash("testing"),
            self.config.testing_prompt_template_sha256,
        )
        check(
            "prompt.refactoring_sha256",
            _prompt_template_hash("refactoring"),
            self.config.refactoring_prompt_template_sha256,
        )
        check("dataset.manifest_id", manifest.manifest_id, self.config.smoke_dataset_manifest_id)
        check("dataset.content_hash", manifest.content_hash, self.config.smoke_dataset_content_hash)
        leakage_path = self.config.dataset_root / "leakage_report.json"
        leakage = json.loads(leakage_path.read_text(encoding="utf-8"))
        if leakage.get("overall_safe") is not True:
            raise BaselineMismatchError("BASELINE_MISMATCH: smoke leakage audit is not safe.")

        collection_metadata = {
            name: identity.model_dump(mode="json")
            for name, identity in sorted(self.config.collection_manifests.items())
        }
        actual_generation_digest = self.config.generation_model_digest
        actual_embedding_digest = self.config.embedding_model_digest
        runtime_validation = "skipped"
        if not self.config.require_runtime_assets:
            if mismatches:
                raise BaselineMismatchError("BASELINE_MISMATCH: " + "; ".join(mismatches))
            return _environment_metadata(
                self.config,
                rag,
                generation_digest=actual_generation_digest,
                embedding_digest=actual_embedding_digest,
                collections=collection_metadata,
                runtime_validation=runtime_validation,
            )

        persist = Path(rag.vector_store.persist_path)
        if not persist.is_dir():
            raise BaselineMismatchError(
                f"BASELINE_MISMATCH: Chroma persistence directory is missing: {persist.as_posix()}"
            )
        manifest_store = CollectionManifestStore(persist)
        for collection in (
            self.config.single_collection,
            *self.config.multi_collections,
        ):
            try:
                collection_manifest = manifest_store.read(collection)
            except IncompatibleCollectionError as exc:
                raise BaselineMismatchError(f"BASELINE_MISMATCH: {exc}") from exc
            _check_collection_identity(
                collection,
                collection_manifest,
                self.config.collection_manifests[collection],
                mismatches,
            )
            check(
                f"collections.{collection}.embedding_provider",
                collection_manifest.embedding_provider,
                self.config.embedding_provider,
            )
            check(
                f"collections.{collection}.embedding_model",
                collection_manifest.embedding_model,
                self.config.embedding_model,
            )
            check(
                f"collections.{collection}.embedding_dimension",
                collection_manifest.embedding_dimension,
                self.config.embedding_dimension,
            )
            check(
                f"collections.{collection}.embedding_model_digest",
                collection_manifest.embedding_model_digest,
                self.config.embedding_model_digest,
            )
            collection_metadata[collection] = {
                "manifest_id": collection_manifest_id(collection_manifest),
                "content_hash": collection_content_hash(collection_manifest),
                "document_count": collection_manifest.document_count,
                "dataset_manifest_ids": sorted(collection_manifest.dataset_manifests),
            }

        if mismatches:
            raise BaselineMismatchError("BASELINE_MISMATCH: " + "; ".join(mismatches))

        generation_provider = create_llm_provider(rag.llm)
        generation_resolver = getattr(generation_provider, "resolve_model_digest", None)
        if not callable(generation_resolver):
            mismatches.append("generation model provider cannot resolve a runtime digest")
        else:
            try:
                actual_generation_digest = str(generation_resolver())
            except RuntimeError as exc:
                raise BaselineMismatchError(
                    f"BASELINE_MISMATCH: generation model digest could not be verified: {exc}"
                ) from exc
            check(
                "generation.model_digest",
                actual_generation_digest,
                self.config.generation_model_digest,
            )
        embedding_provider = create_embedding_provider(rag.embeddings)
        embedding_resolver = getattr(embedding_provider, "resolve_model_digest", None)
        if not callable(embedding_resolver):
            mismatches.append("embedding provider cannot resolve a runtime digest")
        else:
            try:
                actual_embedding_digest = str(embedding_resolver())
            except RuntimeError as exc:
                raise BaselineMismatchError(
                    f"BASELINE_MISMATCH: embedding model digest could not be verified: {exc}"
                ) from exc
            check(
                "embeddings.model_digest",
                actual_embedding_digest,
                self.config.embedding_model_digest,
            )

        if mismatches:
            raise BaselineMismatchError("BASELINE_MISMATCH: " + "; ".join(mismatches))
        return _environment_metadata(
            self.config,
            rag,
            generation_digest=actual_generation_digest,
            embedding_digest=actual_embedding_digest,
            collections=collection_metadata,
            runtime_validation="passed",
        )

    def _load_rag_config(self) -> RagConfig:
        if self._rag_config is None:
            self._rag_config = load_rag_config(self.config.retrieval_config)
        return self._rag_config


def _evaluate(case: SmokeCase, experiment: ExperimentRecord) -> dict[str, Any]:
    response = json.loads(experiment.response)
    prediction = str(
        response.get("generated_tests")
        if case.task == "testing"
        else response.get("refactored_code")
    )
    expected = getattr(case.expected_output, "reference_code", None) or ""
    record = {
        "input": case.input.source_code,
        "expected_output": expected,
        "prediction": prediction,
        "metadata": {"focal_method_name": case.input.focal_method},
    }
    return (
        compute_testing_metrics(record)
        if case.task == "testing"
        else compute_refactoring_metrics(record)
    )


def _run_id(case_id: str, mode: RetrievalMode) -> str:
    return f"{case_id}::{mode.value}"


def _prompt_template_hash(task: str) -> str:
    template = canonical_prompt_template(task)
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def _check_collection_identity(
    name: str,
    manifest: CollectionManifest,
    expected: FrozenCollectionIdentity,
    mismatches: list[str],
) -> None:
    checks = {
        "manifest_id": collection_manifest_id(manifest),
        "content_hash": collection_content_hash(manifest),
        "document_count": manifest.document_count,
        "dataset_manifest_ids": tuple(sorted(manifest.dataset_manifests)),
    }
    expected_values = {
        "manifest_id": expected.manifest_id,
        "content_hash": expected.content_hash,
        "document_count": expected.document_count,
        "dataset_manifest_ids": tuple(sorted(expected.dataset_manifest_ids)),
    }
    for field, actual in checks.items():
        wanted = expected_values[field]
        if actual != wanted:
            mismatches.append(f"collections.{name}.{field}: expected={wanted!r}, actual={actual!r}")


def _environment_metadata(
    config: SmokeExperimentConfig,
    rag: RagConfig,
    *,
    generation_digest: str,
    embedding_digest: str,
    collections: dict[str, Any],
    runtime_validation: str,
) -> dict[str, Any]:
    metadata = {
        "baseline_id": config.baseline_id,
        "baseline_fingerprint": config.baseline_fingerprint,
        "os_runtime": platform.platform(),
        "configured_runtime": config.runtime_environment,
        "runtime_validation": runtime_validation,
        "python_version": sys.version.split()[0],
        "generation_model": config.generation_model,
        "generation_digest": generation_digest,
        "embedding_model": config.embedding_model,
        "embedding_digest": embedding_digest,
        "chroma_path": Path(rag.vector_store.persist_path).as_posix(),
        "collection_ids": collections,
    }
    if config.ollama_num_ctx is not None:
        metadata["ollama_num_ctx"] = config.ollama_num_ctx
    return metadata
