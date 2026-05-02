from pathlib import Path

from llm_ontology.evaluation.metrics import aggregate_scores, load_predictions, token_f1
from llm_ontology.evaluation.report import render_report


def test_token_f1() -> None:
    assert token_f1("a b c", "a b") > 0
    assert token_f1("a", "z") == 0


def test_aggregate_scores() -> None:
    records = [{"reference": "a b", "prediction": "a b"}, {"reference": "a b", "prediction": "a"}]

    scores = aggregate_scores(records)

    assert scores["count"] == 2
    assert scores["exact_match"] == 0.5


def test_load_predictions_and_render_report(tmp_path: Path) -> None:
    path = tmp_path / "predictions.jsonl"
    path.write_text('{"reference": "x", "prediction": "x", "domain": "testing"}\n', encoding="utf-8")

    records = load_predictions(path)
    report = render_report(
        {"experiment": {"name": "demo", "domain": "testing", "method": "fine_tuning"}},
        {"overall": aggregate_scores(records)},
    )

    assert records[0]["domain"] == "testing"
    assert "Experiment Report: demo" in report
