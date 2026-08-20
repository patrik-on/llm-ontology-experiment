from __future__ import annotations

from typing import Any


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r\n", "\n").split())


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: normalize_text(value) for key, value in record.items()}


def is_non_empty_pair(input_text: str, output_text: str) -> bool:
    return bool(input_text.strip() and output_text.strip())
