from __future__ import annotations


def format_training_prompt(example: dict) -> str:
    return (
        "### Instruction:\n"
        f"{example['instruction']}\n\n"
        "### Input:\n"
        f"{example['input']}\n\n"
        "### Response:\n"
        f"{example['output']}"
    )


def format_inference_prompt(instruction: str, input_text: str) -> str:
    return (
        "### Instruction:\n"
        f"{instruction}\n\n"
        "### Input:\n"
        f"{input_text}\n\n"
        "### Response:\n"
    )
