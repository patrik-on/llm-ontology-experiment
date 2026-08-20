from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.benchmarks.swe_refactor import load_swe_refactor


def test_swe_refactor_falls_back_to_whole_file_source(tmp_path: Path) -> None:
    payload = [
        {
            "type": "Move And Inline Method",
            "isPureRefactoring": True,
            "uniqueId": "fallback-1",
            "sourceCodeBeforeRefactoring": "",
            "sourceCodeBeforeForWhole": "class Before { void run() {} }",
            "sourceCodeAfterRefactoring": "class After { void run() {} }",
        }
    ]
    (tmp_path / "pure_refactoring_data.json").write_text(json.dumps(payload), encoding="utf-8")

    case = load_swe_refactor(tmp_path)[0]

    assert case.input_text == "class Before { void run() {} }"
    assert case.metadata["used_whole_file_fallback"] is True
