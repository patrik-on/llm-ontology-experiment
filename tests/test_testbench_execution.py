from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from llm_ontology.benchmarks.testbench_execution import (
    execute_testbench_plan,
    generated_class_name,
    parse_project_java_homes,
    plan_testbench_record,
    strip_markdown_fence,
)


def prediction_record() -> dict[str, object]:
    return {
        "id": "testbench:demo:Calculator:add:0",
        "benchmark": "testbench",
        "prediction": "```java\npackage org.example;\npublic class GeneratedCalculatorTest {}\n```",
        "metadata": {
            "project": "demo",
            "package": "org.example",
            "relative_path": "demo/src/main/java/org/example/Calculator.java",
            "execute_path": "demo",
        },
    }


def benchmark_root(tmp_path: Path) -> Path:
    root = tmp_path / "TestBench-main"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "pom.xml").write_text("<project/>", encoding="utf-8")
    return root


def test_code_fence_and_generated_class_parsing() -> None:
    code = strip_markdown_fence("```java\npublic final class DemoTest {}\n```")

    assert code == "public final class DemoTest {}"
    assert generated_class_name(code) == "DemoTest"


def test_plan_resolves_build_and_test_paths_inside_benchmark(tmp_path: Path) -> None:
    root = benchmark_root(tmp_path)

    plan = plan_testbench_record(prediction_record(), benchmark_root=root)

    assert plan.build_root == (root / "demo").resolve()
    assert plan.test_file == (root / "demo/src/test/java/org/example/GeneratedCalculatorTest.java").resolve()
    assert plan.maven_args[-1] == "test"
    assert "-Dtest=GeneratedCalculatorTest" in plan.maven_args


def test_plan_rejects_path_traversal(tmp_path: Path) -> None:
    root = benchmark_root(tmp_path)
    record = prediction_record()
    metadata = dict(record["metadata"])  # type: ignore[arg-type]
    metadata["execute_path"] = "../outside"
    record["metadata"] = metadata

    with pytest.raises(ValueError, match="Unsafe build root"):
        plan_testbench_record(record, benchmark_root=root)


def test_dry_run_does_not_write_generated_test(tmp_path: Path) -> None:
    plan = plan_testbench_record(prediction_record(), benchmark_root=benchmark_root(tmp_path))

    result = execute_testbench_plan(plan, dry_run=True)

    assert result["status"] == "planned"
    assert not plan.test_file.exists()


def test_execution_restores_colliding_test_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = benchmark_root(tmp_path)
    plan = plan_testbench_record(prediction_record(), benchmark_root=root)
    plan.test_directory.mkdir(parents=True)
    original = b"package org.example; public class GeneratedCalculatorTest { int original; }"
    plan.test_file.write_bytes(original)
    fake_maven = tmp_path / "mvn.exe"
    fake_maven.write_bytes(b"placeholder")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert plan.test_file.read_text(encoding="utf-8") == plan.code
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="BUILD SUCCESS", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_testbench_plan(plan, maven_executable=str(fake_maven))

    assert result["status"] == "accepted"
    assert plan.test_file.read_bytes() == original


def test_project_java_home_parser() -> None:
    assert parse_project_java_homes(["Java=C:/jdk17", "apollo=C:/jdk8"]) == {
        "Java": "C:/jdk17",
        "apollo": "C:/jdk8",
    }
    with pytest.raises(ValueError, match="PROJECT=PATH"):
        parse_project_java_homes(["invalid"])
