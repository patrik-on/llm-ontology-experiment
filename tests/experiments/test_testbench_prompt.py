from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.benchmarks.testbench import load_testbench


def test_testbench_prompt_contains_compilation_target_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "source_file_parser"
    source_dir.mkdir()
    record = {
        "project_name": "demo",
        "package": "org.example",
        "source_code": "int add(int a, int b) { return a + b; }",
        "class_name": "Calculator",
        "method_name": "add",
        "simple_context": "class Calculator {}",
        "full_context": "package org.example; class Calculator {}",
    }
    (source_dir / "demo_out.json").write_text(json.dumps([record]), encoding="utf-8")

    case = load_testbench(tmp_path, context_level="source")[0]

    assert "Target package: org.example" in case.input_text
    assert "Target class: Calculator" in case.input_text
    assert "Target method: add" in case.input_text
    assert "complete, compilable JUnit Jupiter test class" in case.instruction
    assert "Return only Java source code" in case.instruction
