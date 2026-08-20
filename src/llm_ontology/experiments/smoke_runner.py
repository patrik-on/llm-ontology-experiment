from __future__ import annotations

import json
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
from llm_ontology.experiments.smoke_models import (
    SmokeExperimentConfig,
    SmokeRunRecord,
    SmokeRunResult,
    SmokeSelection,
)
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
from llm_ontology.retrieval.config import RagConfig, load_rag_config
from llm_ontology.retrieval.factory import create_llm_provider, create_vector_store
from llm_ontology.retrieval.models import RetrievalMode
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter


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
        self._preflight(cases)
        fairness = audit_prompt_fairness(cases)
        if not fairness["passed"]:
            write_smoke_reports(self.config, planned_runs=0, fairness_audit=fairness)
            raise RuntimeError("Canonical prompt fairness audit failed.")

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
                planned_runs=len(planned),
                output_dir=self.config.output_dir,
            )

        runs_path = self.config.output_dir / "runs.jsonl"
        latest = latest_run_records(read_run_history(runs_path))
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
            and (
                not selection.difficulties
                or case.difficulty.value in selection.difficulties
            )
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
            allowed_splits=list(self.config.allowed_splits),
            tokenizer_model=self.config.tokenizer_model,
            tokenizer_revision=self.config.tokenizer_revision,
            token_counting_method="huggingface_tokenizer",
            total_context_tokens=self.config.total_context_tokens,
            reserved_output_tokens=self.config.reserved_output_tokens,
            safety_margin_tokens=self.config.safety_margin_tokens,
            random_seed=self.config.random_seed,
            results_path=self.config.output_dir / "runs.jsonl",
            prompt_artifacts_dir=self.config.output_dir / "prompts" / case.id / mode.value,
        )

    def _preflight(self, cases: list[SmokeCase]) -> None:
        if len(cases) != 24:
            raise ValueError(f"Smoke preflight expected 24 cases, found {len(cases)}.")
        rag = self._load_rag_config()
        if rag.runtime.environment != "wsl" or rag.runtime.status != "current":
            raise ValueError("Smoke baseline requires the current WSL retrieval runtime.")
        if rag.llm.model != "qwen2.5-coder:7b" or rag.embeddings.model != "bge-m3":
            raise ValueError("Smoke baseline model or embedding model differs from the frozen baseline.")
        leakage_path = self.config.dataset_root / "leakage_report.json"
        leakage = json.loads(leakage_path.read_text(encoding="utf-8"))
        if leakage.get("overall_safe") is not True:
            raise ValueError("Smoke leakage audit is not safe.")
        if not self.config.require_runtime_assets:
            return
        persist = Path(rag.vector_store.persist_path)
        if not persist.is_dir():
            raise FileNotFoundError(f"Chroma persistence directory is missing: {persist}")
        for collection in (
            self.config.single_collection,
            *self.config.multi_collections,
        ):
            manifest_path = persist / "manifests" / f"{collection}.json"
            if not manifest_path.is_file():
                raise FileNotFoundError(f"Collection manifest is missing: {manifest_path}")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if int(payload.get("document_count", 0)) <= 0:
                raise ValueError(f"Collection {collection!r} has no indexed documents.")

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
