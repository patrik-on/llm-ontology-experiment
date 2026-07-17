from __future__ import annotations


def format_inference_prompt(instruction: str, input_text: str) -> str:
    return (
        "### Instruction:\n"
        f"{instruction}\n\n"
        "### Input:\n"
        f"{input_text}\n\n"
        "### Response:\n"
    )


def format_prompt(example: dict) -> str:
    return format_inference_prompt(example["instruction"], example["input"])


def format_training_prompt(example: dict, eos_token: str = "") -> str:
    return f"{format_prompt(example)}{example['output']}{eos_token or ''}"
