from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_ontology.benchmarks.contracts import BenchmarkCase


BENCHMARK_NAME = "testbench"
CONTEXT_LEVELS = ("source", "simple", "full")
DEFAULT_ROOT = Path("benchmarks/TestBench-main")
TESTING_INSTRUCTION = (
    "Generate one complete, compilable JUnit Jupiter test class for the target Java method. "
    "Include the package declaration, required imports, test class, and meaningful assertions. "
    "Return only Java source code without explanations."
)


def _slug(value: Any) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value).strip())
    return cleaned.strip("-") or "unknown"


def _render_input(record: dict[str, Any], context_level: str) -> str:
    source = str(record.get("source_code", "")).strip()
    sections = [
        f"Target package: {str(record.get('package', '')).strip()}",
        f"Target class: {str(record.get('class_name', '')).strip()}",
        f"Target method: {str(record.get('method_name', '')).strip()}",
        f"\nJava source under test:\n{source}",
    ]
    if context_level != "source":
        context = str(record.get(f"{context_level}_context", "")).strip()
        if context:
            sections.append(f"\n{context_level.title()} project context:\n{context}")
    return "\n".join(sections)


def load_testbench(
    root: str | Path = DEFAULT_ROOT,
    *,
    context_level: str = "source",
) -> list[BenchmarkCase]:
    """Load TestBench cases without importing its model-specific scripts."""

    if context_level not in CONTEXT_LEVELS:
        raise ValueError(f"Unsupported TestBench context level {context_level!r}; expected one of {CONTEXT_LEVELS}.")
    source_dir = Path(root) / "source_file_parser"
    files = sorted(source_dir.glob("*_out.json"))
    if not files:
        raise FileNotFoundError(f"No TestBench parser outputs found in {source_dir}")

    cases: list[BenchmarkCase] = []
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON list in {path}")
        for index, record in enumerate(payload):
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object at {path}:{index}")
            project = _slug(record.get("project_name", path.stem.removesuffix("_out")))
            class_name = _slug(record.get("class_name", "class"))
            method_name = _slug(record.get("method_name", "method"))
            cases.append(
                BenchmarkCase(
                    case_id=f"testbench:{project}:{class_name}:{method_name}:{index}",
                    benchmark=BENCHMARK_NAME,
                    task="testing",
                    instruction=TESTING_INSTRUCTION,
                    input_text=_render_input(record, context_level),
                    metadata={
                        "project": str(record.get("project_name", "")),
                        "package": str(record.get("package", "")),
                        "class_name": str(record.get("class_name", "")),
                        "method_name": str(record.get("method_name", "")),
                        "file_name": str(record.get("file_name", "")),
                        "relative_path": str(record.get("relative_path", "")),
                        "execute_path": str(record.get("execute_path", "")),
                        "context_level": context_level,
                        "source_file": path.as_posix(),
                    },
                )
            )
    return cases
