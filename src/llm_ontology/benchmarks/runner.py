from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from llm_ontology.benchmarks.contracts import BenchmarkCase
from llm_ontology.inference.approach_runner import prepare_prompt


Generator = Callable[[str], str]


def run_cases(
    cases: Iterable[BenchmarkCase],
    *,
    generator: Generator | None = None,
) -> list[dict[str, Any]]:
    """Prepare direct prompts and optionally generate benchmark predictions."""

    output: list[dict[str, Any]] = []
    for case in cases:
        prepared = prepare_prompt(
            "direct",
            task=case.task,
            instruction=case.instruction,
            input_text=case.input_text,
        )
        record = case.as_record()
        record.update({"approach": prepared.approach, "prompt": prepared.text})
        if generator is not None:
            record["prediction"] = generator(prepared.text)
        output.append(record)
    return output
