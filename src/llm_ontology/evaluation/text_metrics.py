from __future__ import annotations

import difflib
import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def exact_match(reference: str, prediction: str) -> float:
    return float((reference or "").strip() == (prediction or "").strip())


def normalized_exact_match(reference: str, prediction: str) -> float:
    return float(normalize_text(reference) == normalize_text(prediction))


def character_length(text: str) -> int:
    return len(text or "")


def token_count_simple(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def normalized_edit_similarity(reference: str, prediction: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(reference), normalize_text(prediction)).ratio()


def output_non_empty(prediction: str) -> bool:
    return bool((prediction or "").strip())


def output_differs_from_input(input_text: str, prediction: str) -> bool:
    return normalize_text(input_text) != normalize_text(prediction)


def basic_text_metrics(input_text: str, expected_output: str, prediction: str) -> dict[str, float | int | bool]:
    return {
        "exact_match": exact_match(expected_output, prediction),
        "normalized_exact_match": normalized_exact_match(expected_output, prediction),
        "prediction_char_length": character_length(prediction),
        "prediction_token_count": token_count_simple(prediction),
        "normalized_edit_similarity": normalized_edit_similarity(expected_output, prediction),
        "output_non_empty": output_non_empty(prediction),
        "output_differs_from_input": output_differs_from_input(input_text, prediction),
    }
