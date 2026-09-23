from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_ontology.evaluation.experiment_log import ExperimentRecord
from llm_ontology.experiments.baseline import (
    BaselineMismatchError,
    compute_baseline_fingerprint,
)
from llm_ontology.experiments.smoke_models import (
    SmokeRunRecord,
    SmokeSelection,
    load_smoke_experiment_config,
)
from llm_ontology.experiments.smoke_runner import SmokeExperimentRunner
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentConfig
from llm_ontology.retrieval.models import RetrievalMode, RetrievalTrace


REQUIRED_OUTPUTS = {
    "runs.jsonl",
    "summary.json",
    "summary.csv",
    "case_comparison.json",
    "case_comparison.csv",
    "retrieval_analysis.json",
    "failure_analysis.json",
    "fairness_audit.json",
    "report.md",
    "effective_config.yaml",
    "environment.json",
}


def _config(tmp_path: Path):
    return load_smoke_experiment_config("configs/experiments/baseline_v1.yaml").model_copy(
        update={"output_dir": tmp_path, "require_runtime_assets": False}
    )


def _v2_config(tmp_path: Path):
    return load_smoke_experiment_config("configs/experiments/baseline_v2.yaml").model_copy(
        update={"output_dir": tmp_path, "require_runtime_assets": False}
    )


def _success(config: RagExperimentConfig, case: ExperimentCase) -> ExperimentRecord:
    task = config.canonical_task.value  # type: ignore[union-attr]
    answer = (
        {
            "task_type": "testing",
            "analysis_summary": "covers the method",
            "generated_tests": "@Test void works() { assertTrue(true); }",
        }
        if task == "testing"
        else {
            "task_type": "refactoring",
            "analysis_summary": "preserves behavior",
            "refactored_code": case.input_text + "\n",
        }
    )
    return ExperimentRecord(
        configuration=config.model_dump(mode="json"),
        dataset_version=config.dataset_version,
        embedding_model=config.embedding_model,
        embedding_version=config.embedding_revision,
        llm_model=config.llm_model,
        llm_version=config.llm_version,
        retrieval_parameters={"mode": config.retrieval_mode.value},
        random_seed=config.random_seed,
        input={"case_id": case.case_id, "input_text": case.input_text},
        retrieval_trace=RetrievalTrace(
            query=case.input_text,
            selected_collections=(
                list(config.collections)
                if config.collections
                else ([] if config.collection is None else [config.collection])
            ),
        ),
        response=json.dumps(answer),
        requested_task=task,
        canonical_task=task,
        retrieval_mode=config.retrieval_mode.value,
        prompt_template_version="canonical-se-prompt-v2",
        prompt_template_sha256="a" * 64,
        normalized_prompt_sha256="b" * 64,
        full_prompt_sha256="c" * 64,
    )


def test_dry_run_validates_default_72_cell_matrix_and_writes_reports(tmp_path: Path) -> None:
    result = SmokeExperimentRunner(_config(tmp_path), case_executor=_success).run(dry_run=True)

    assert result.preflight_passed is True
    assert result.fairness_passed is True
    assert result.planned_runs == 72
    assert REQUIRED_OUTPUTS.issubset({path.name for path in tmp_path.iterdir()})
    fairness = json.loads((tmp_path / "fairness_audit.json").read_text(encoding="utf-8"))
    assert fairness["passed"] is True
    assert fairness["cases_checked"] == 24
    assert result.baseline_fingerprint_matched is True
    effective = (tmp_path / "effective_config.yaml").read_text(encoding="utf-8")
    assert f"baseline_fingerprint: {result.baseline_fingerprint}" in effective
    environment = json.loads((tmp_path / "environment.json").read_text(encoding="utf-8"))
    assert environment["chroma_path"] == "data/chroma/ollama_bge_m3"


def test_six_run_pilot_is_resumable_and_uses_all_three_modes(tmp_path: Path) -> None:
    calls: list[tuple[str, RetrievalMode]] = []

    def execute(config: RagExperimentConfig, case: ExperimentCase) -> ExperimentRecord:
        calls.append((case.case_id, config.retrieval_mode))
        return _success(config, case)

    runner = SmokeExperimentRunner(_config(tmp_path), case_executor=execute)
    selection = SmokeSelection(case_ids=("testing_easy_001", "refactoring_easy_001"))
    first = runner.run(selection)
    second = runner.run(selection)

    assert first.executed_runs == first.successful_runs == 6
    assert first.failed_runs == 0
    assert second.executed_runs == 0
    assert second.skipped_runs == 6
    assert len(calls) == 6
    assert {mode for _, mode in calls} == {
        RetrievalMode.NO_RAG,
        RetrievalMode.SINGLE_COLLECTION_RAG,
        RetrievalMode.MULTI_COLLECTION_RAG,
    }
    assert len((tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()) == 6
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["successful_run_ids"] == 6
    assert summary["failed_run_ids"] == 0


def test_retry_failed_appends_new_attempt_without_restarting_successes(tmp_path: Path) -> None:
    failed_once = True

    def execute(config: RagExperimentConfig, case: ExperimentCase) -> ExperimentRecord:
        nonlocal failed_once
        if failed_once:
            failed_once = False
            raise RuntimeError("fixture failure")
        return _success(config, case)

    runner = SmokeExperimentRunner(_config(tmp_path), case_executor=execute)
    selection = SmokeSelection(
        case_ids=("testing_easy_001",),
        modes=(RetrievalMode.NO_RAG,),
    )
    first = runner.run(selection)
    retry = runner.run(selection.model_copy(update={"retry_failed": True}))

    assert first.failed_runs == 1
    assert retry.successful_runs == 1
    history = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert [item["attempt"] for item in history] == [1, 2]
    assert [item["status"] for item in history] == ["failed", "success"]
    failures = json.loads((tmp_path / "failure_analysis.json").read_text(encoding="utf-8"))
    assert failures["failure_count"] == 0
    assert failures["historical_failure_attempt_count"] == 1


def test_baseline_fingerprint_is_portable_but_changes_with_contract() -> None:
    config = load_smoke_experiment_config("configs/experiments/baseline_v1.yaml")

    assert compute_baseline_fingerprint(config) == config.baseline_fingerprint
    moved_output = config.model_copy(
        update={"output_dir": Path("some/other/machine/output"), "require_runtime_assets": False}
    )
    assert compute_baseline_fingerprint(moved_output) == config.baseline_fingerprint
    changed_top_k = config.model_copy(update={"top_k": 6})
    assert compute_baseline_fingerprint(changed_top_k) != config.baseline_fingerprint


def test_v2_filters_task_shortens_documents_and_uses_top_k_three(
    tmp_path: Path,
) -> None:
    captured: list[RagExperimentConfig] = []

    def execute(config: RagExperimentConfig, case: ExperimentCase) -> ExperimentRecord:
        captured.append(config)
        return _success(config, case)

    result = SmokeExperimentRunner(_v2_config(tmp_path), case_executor=execute).run(
        SmokeSelection(
            case_ids=("testing_easy_001", "refactoring_easy_001"),
        )
    )

    assert result.executed_runs == 6
    assert all(config.top_k == 3 for config in captured)
    assert all(config.per_collection_top_k == 3 for config in captured)
    assert all(config.max_retrieved_document_tokens == 768 for config in captured)
    for config in captured:
        expected_filter = (
            {}
            if config.retrieval_mode == RetrievalMode.NO_RAG
            else {"task": config.canonical_task.value}  # type: ignore[union-attr]
        )
        assert config.metadata_filter == expected_filter

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["evaluation_metric_contract"] == "canonical_finetuning_eval_metrics"
    testing = next(row for row in summary["by_task_mode"] if row["task"] == "testing")
    refactoring = next(row for row in summary["by_task_mode"] if row["task"] == "refactoring")
    assert "avg_test_quality_score" in testing
    assert "avg_coverage_proxy_score" in testing
    assert "avg_code_health_delta_score" in refactoring
    assert "avg_cohesion_proxy_score" in refactoring
    assert "avg_coupling_proxy_score" in refactoring
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Code health" in report


def test_v2_context_contract_and_fingerprint_are_valid() -> None:
    config = load_smoke_experiment_config("configs/experiments/baseline_v2.yaml")

    assert config.baseline_id == "baseline_v2"
    assert config.ollama_num_ctx == 32768
    assert config.reserved_output_tokens == 4096
    assert config.enforce_retrieval_token_budget is True
    assert config.fail_on_prompt_budget_exceeded is True
    assert compute_baseline_fingerprint(config) == config.baseline_fingerprint


def test_current_prompt_must_match_the_frozen_hash(tmp_path: Path) -> None:
    config = _config(tmp_path).model_copy(update={"testing_prompt_template_sha256": "0" * 64})
    config = config.model_copy(
        update={"baseline_fingerprint": compute_baseline_fingerprint(config)}
    )

    with pytest.raises(BaselineMismatchError, match="prompt.testing_sha256"):
        SmokeExperimentRunner(config, case_executor=_success).run(dry_run=True)


def test_reports_exclude_historical_runs_from_another_fingerprint(tmp_path: Path) -> None:
    legacy = SmokeRunRecord(
        baseline_id="baseline_v1",
        baseline_fingerprint="old-fingerprint",
        run_id="testing_easy_001::no_rag",
        case_id="testing_easy_001",
        task="testing",
        difficulty="easy",
        mode=RetrievalMode.NO_RAG,
        status="success",
        attempt=1,
    )
    (tmp_path / "runs.jsonl").write_text(legacy.model_dump_json() + "\n", encoding="utf-8")

    SmokeExperimentRunner(_config(tmp_path), case_executor=_success).run(dry_run=True)

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["recorded_run_ids"] == 0
    assert summary["history_records"] == 0
    assert summary["raw_history_records"] == 1
    assert summary["excluded_history_records"] == 1
