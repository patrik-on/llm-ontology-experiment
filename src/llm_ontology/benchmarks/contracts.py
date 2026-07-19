from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One normalized, immutable benchmark input."""

    case_id: str
    benchmark: str
    task: str
    instruction: str
    input_text: str
    reference_output: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("Benchmark case_id must not be empty.")
        if self.task not in {"testing", "refactoring"}:
            raise ValueError(f"Unsupported benchmark task: {self.task!r}")
        if not self.instruction.strip() or not self.input_text.strip():
            raise ValueError(f"Benchmark case {self.case_id!r} has an empty prompt field.")

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "benchmark": self.benchmark,
            "domain": self.task,
            "instruction": self.instruction,
            "input": self.input_text,
            "reference_output": self.reference_output,
            "metadata": dict(self.metadata),
        }
