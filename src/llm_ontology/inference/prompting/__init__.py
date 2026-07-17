"""Shared prompt formatting used by training and generation approaches."""

from llm_ontology.inference.prompting.instruction import (
    format_inference_prompt,
    format_prompt,
    format_training_prompt,
)

__all__ = ["format_inference_prompt", "format_prompt", "format_training_prompt"]
