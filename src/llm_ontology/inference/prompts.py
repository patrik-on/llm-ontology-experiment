from __future__ import annotations

from collections.abc import Iterable

from llm_ontology.approaches import RetrievedContext
from llm_ontology.inference.approach_runner import prepare_prompt
from llm_ontology.inference.prompting import format_training_prompt


def build_prompt(
    record: dict[str, str],
    approach: str = "direct",
    contexts: Iterable[RetrievedContext] = (),
) -> str:
    return prepare_prompt(
        approach,
        task=str(record.get("domain", "unknown")),
        instruction=record["instruction"],
        input_text=record["input"],
        contexts=contexts,
    ).text


def build_training_text(record: dict[str, str]) -> str:
    return format_training_prompt(record)
