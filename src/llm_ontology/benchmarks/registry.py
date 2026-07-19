from __future__ import annotations

from pathlib import Path

from llm_ontology.benchmarks.contracts import BenchmarkCase
from llm_ontology.benchmarks.swe_refactor import DEFAULT_ROOT as SWE_REFACTOR_ROOT
from llm_ontology.benchmarks.swe_refactor import load_swe_refactor
from llm_ontology.benchmarks.testbench import DEFAULT_ROOT as TESTBENCH_ROOT
from llm_ontology.benchmarks.testbench import load_testbench


def available_benchmarks() -> tuple[str, ...]:
    return ("testbench", "swe_refactor")


def load_benchmark(
    name: str,
    *,
    root: str | Path | None = None,
    context_level: str = "source",
) -> list[BenchmarkCase]:
    normalized = name.strip().lower().replace("-", "_")
    if normalized == "testbench":
        return load_testbench(root or TESTBENCH_ROOT, context_level=context_level)
    if normalized == "swe_refactor":
        return load_swe_refactor(root or SWE_REFACTOR_ROOT)
    raise ValueError(f"Unknown benchmark {name!r}; available: {', '.join(available_benchmarks())}")
