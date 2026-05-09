from __future__ import annotations

from llm_ontology.finetuning.prompt_formatter import format_inference_prompt, format_training_prompt


def build_prompt(record: dict[str, str]) -> str:
    return format_inference_prompt(record["instruction"], record["input"])


def build_training_text(record: dict[str, str]) -> str:
    return format_training_prompt(record)
