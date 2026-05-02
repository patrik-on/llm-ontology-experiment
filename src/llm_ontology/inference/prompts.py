from __future__ import annotations


def build_prompt(record: dict[str, str]) -> str:
    return (
        "### Instruction:\n"
        f"{record['instruction']}\n\n"
        "### Input:\n"
        f"{record['input']}\n\n"
        "### Response:\n"
    )


def build_training_text(record: dict[str, str]) -> str:
    return f"{build_prompt(record)}{record['output']}"
