import pytest
from llm_ontology.benchmarks import methods2test_hundred_report as report
from llm_ontology.benchmarks.defects4j_execution import write_json


def test_finalizer_rejects_partial_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "verify", lambda root: None)
    monkeypatch.setattr(report, "selection", lambda root: {"ids": ["x"], "cases": [{"id": "x"}]})
    write_json(
        tmp_path / "cases/x/raw-private.json", {"raw": {"test_case": {"body": "private oracle"}}}
    )
    with pytest.raises(ValueError, match="incomplete_400_cell_matrix"):
        report.finalize(tmp_path)


def test_finalizer_rejects_gold_in_actual_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "verify", lambda root: None)
    monkeypatch.setattr(report, "selection", lambda root: {"ids": ["x"], "cases": [{"id": "x"}]})
    write_json(
        tmp_path / "cases/x/raw-private.json", {"raw": {"test_case": {"body": "private oracle"}}}
    )
    write_json(
        tmp_path / "cases/x/predictions/qwen_base/dispatch.json",
        {
            "id": "x",
            "arm": "qwen_base",
            "charged_to_budget": True,
            "request": {"prompt": "private oracle"},
        },
    )
    with pytest.raises(ValueError, match="gold_entered_prompt"):
        report.finalize(tmp_path)
