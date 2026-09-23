from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_ontology.evaluation.run_layout import (
    EvaluationRunLayout,
    require_canonical_evaluation_path,
)


def test_evaluation_layout_uses_one_canonical_run_root(tmp_path: Path) -> None:
    layout = EvaluationRunLayout("v2_final", runs_root=tmp_path / "runs")

    layout.prepare()

    assert layout.root == tmp_path / "runs" / "v2_final"
    assert layout.predictions.is_dir()
    assert layout.metrics.is_dir()
    assert layout.reports.is_dir()
    assert layout.samples.is_dir()
    assert layout.analysis.is_dir()


@pytest.mark.parametrize("run_id", ("../escape", "Evaluation V2", "x", "a/b"))
def test_evaluation_layout_rejects_unsafe_run_ids(run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        EvaluationRunLayout(run_id)


def test_run_manifest_preserves_creation_time_and_updates_status(tmp_path: Path) -> None:
    layout = EvaluationRunLayout("pilot_01", runs_root=tmp_path / "runs")
    layout.write_manifest(status="running", metadata={"limit": 5})
    first = json.loads(layout.manifest_path.read_text(encoding="utf-8"))

    layout.write_manifest(status="completed", metadata={"models": ["baseline"]})
    final = json.loads(layout.manifest_path.read_text(encoding="utf-8"))

    assert final["status"] == "completed"
    assert final["created_at"] == first["created_at"]
    assert final["metadata"] == {"limit": 5, "models": ["baseline"]}
    assert final["layout"]["predictions"] == "predictions"


def test_cli_output_guard_rejects_new_root_level_evaluation_directory() -> None:
    accepted = require_canonical_evaluation_path(
        "artifacts/evaluation/runs/pilot_01/predictions/testing"
    )

    assert accepted.name == "testing"
    with pytest.raises(ValueError, match="artifacts/evaluation/runs"):
        require_canonical_evaluation_path("evaluation_new/predictions")


def test_repository_root_contains_no_legacy_evaluation_directories() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    legacy = sorted(
        path.name
        for path in repository_root.iterdir()
        if path.is_dir() and path.name.startswith("evaluation")
    )

    assert legacy == []
