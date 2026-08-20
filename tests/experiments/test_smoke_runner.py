from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.evaluation.experiment_log import ExperimentRecord
from llm_ontology.experiments.smoke_models import (
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
}


def _config(tmp_path: Path):
    return load_smoke_experiment_config("configs/experiments/baseline_v1.yaml").model_copy(
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


def test_six_run_pilot_is_resumable_and_uses_all_three_modes(tmp_path: Path) -> None:
    calls: list[tuple[str, RetrievalMode]] = []

    def execute(config: RagExperimentConfig, case: ExperimentCase) -> ExperimentRecord:
        calls.append((case.case_id, config.retrieval_mode))
        return _success(config, case)

    runner = SmokeExperimentRunner(_config(tmp_path), case_executor=execute)
    selection = SmokeSelection(
        case_ids=("testing_easy_001", "refactoring_easy_001")
    )
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
