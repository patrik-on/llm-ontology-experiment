"""Read-only adapters for external software-engineering benchmarks."""

from llm_ontology.benchmarks.contracts import BenchmarkCase
from llm_ontology.benchmarks.registry import available_benchmarks, load_benchmark

__all__ = ["BenchmarkCase", "available_benchmarks", "load_benchmark"]
