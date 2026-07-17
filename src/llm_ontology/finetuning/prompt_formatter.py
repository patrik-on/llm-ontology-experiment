"""Compatibility imports for the original fine-tuning prompt module path."""

from llm_ontology.inference.prompting import (
    format_inference_prompt,
    format_prompt,
    format_training_prompt,
)

__all__ = ["format_inference_prompt", "format_prompt", "format_training_prompt"]
