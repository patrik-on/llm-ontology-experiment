from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.benchmarks.contracts import BenchmarkCase


BENCHMARK_NAME = "swe_refactor"
DEFAULT_ROOT = Path("benchmarks/swe-refactor/SWE-Refactor")


def _first_text(record: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return ""


def load_swe_refactor(root: str | Path = DEFAULT_ROOT) -> list[BenchmarkCase]:
    """Load the pure SWE-Refactor examples as normalized refactoring cases."""

    path = Path(root) / "pure_refactoring_data.json"
    if not path.is_file():
        raise FileNotFoundError(f"SWE-Refactor data file does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")

    cases: list[BenchmarkCase] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object at {path}:{index}")
        if not record.get("isPureRefactoring", False):
            continue
        refactoring_type = str(record.get("type", "unspecified refactoring")).strip()
        unique_id = str(record.get("uniqueId", "")).strip() or str(index)
        input_text = _first_text(record, "sourceCodeBeforeRefactoring", "sourceCodeBeforeForWhole")
        reference_output = _first_text(record, "sourceCodeAfterRefactoring", "sourceCodeAfterForWhole")
        cases.append(
            BenchmarkCase(
                case_id=f"swe-refactor:{unique_id}",
                benchmark=BENCHMARK_NAME,
                task="refactoring",
                instruction=(
                    "Refactor the supplied Java code while preserving its behavior. "
                    f"Requested refactoring type: {refactoring_type}. Return the refactored code."
                ),
                input_text=input_text,
                reference_output=reference_output,
                metadata={
                    "refactoring_type": refactoring_type,
                    "project": str(record.get("projectName", "")),
                    "commit_sha": str(record.get("commitId", "")),
                    "file_path_before": str(record.get("filePathBefore", "")),
                    "class_name_before": str(record.get("classNameBefore", "")),
                    "method_name_before": str(record.get("methodNameBefore", "")),
                    "compile_result_before": record.get("compileResultBefore"),
                    "compile_result_current": record.get("compileResultCurrent"),
                    "has_test": record.get("hasTestC"),
                    "used_whole_file_fallback": not bool(str(record.get("sourceCodeBeforeRefactoring", "")).strip()),
                    "source_file": path.as_posix(),
                },
            )
        )
    return cases
