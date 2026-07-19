from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.benchmarks.runner import run_cases
from llm_ontology.benchmarks.swe_refactor import load_swe_refactor
from llm_ontology.benchmarks.testbench import load_testbench


def test_testbench_adapter_supports_input_context_levels(tmp_path: Path) -> None:
    source_dir = tmp_path / "source_file_parser"
    source_dir.mkdir()
    payload = [
        {
            "project_name": "demo",
            "file_name": "Calculator.java",
            "relative_path": "src/Calculator.java",
            "execute_path": "pom.xml",
            "source_code": "class Calculator { int add() { return 2; } }",
            "class_name": "Calculator",
            "method_name": "add",
            "simple_context": "Uses integer arithmetic.",
            "full_context": "Full project dependency context.",
        }
    ]
    (source_dir / "demo_out.json").write_text(json.dumps(payload), encoding="utf-8")

    source_case = load_testbench(tmp_path, context_level="source")[0]
    full_case = load_testbench(tmp_path, context_level="full")[0]

    assert source_case.task == "testing"
    assert source_case.reference_output == ""
    assert "Full project dependency context" not in source_case.input_text
    assert "Full project dependency context" in full_case.input_text


def test_swe_refactor_adapter_keeps_reference_and_metadata(tmp_path: Path) -> None:
    payload = [
        {
            "type": "Extract Method",
            "isPureRefactoring": True,
            "uniqueId": "r-1",
            "sourceCodeBeforeRefactoring": "class A { void a() { one(); two(); } }",
            "sourceCodeAfterRefactoring": "class A { void a() { both(); } void both() { one(); two(); } }",
            "projectName": "demo",
            "commitId": "abc",
        },
        {"isPureRefactoring": False},
    ]
    (tmp_path / "pure_refactoring_data.json").write_text(json.dumps(payload), encoding="utf-8")

    cases = load_swe_refactor(tmp_path)

    assert len(cases) == 1
    assert cases[0].task == "refactoring"
    assert "both()" in cases[0].reference_output
    assert cases[0].metadata["commit_sha"] == "abc"


def test_direct_runner_prepares_prompt_and_optional_prediction(tmp_path: Path) -> None:
    source_dir = tmp_path / "source_file_parser"
    source_dir.mkdir()
    payload = [
        {
            "project_name": "demo",
            "source_code": "class Calculator { int add(int a, int b) { return a + b; } }",
            "class_name": "Calculator",
            "method_name": "add",
        }
    ]
    (source_dir / "demo_out.json").write_text(json.dumps(payload), encoding="utf-8")
    cases = load_testbench(tmp_path)

    results = run_cases(cases, generator=lambda prompt: "generated" if "Calculator" in prompt else "")

    assert results[0]["approach"] == "direct"
    assert results[0]["prediction"] == "generated"
    assert "Calculator" in results[0]["prompt"]
    assert "retrieval_trace" not in results[0]
