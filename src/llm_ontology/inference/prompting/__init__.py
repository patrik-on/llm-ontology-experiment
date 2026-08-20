"""Shared prompt formatting used by training and generation approaches."""

from llm_ontology.inference.prompting.canonical import (
    EVIDENCE_PLACEHOLDER,
    PROMPT_TEMPLATE_VERSION,
    CanonicalPromptBuilder,
    canonical_prompt_template,
    normalize_retrieved_evidence,
)
from llm_ontology.inference.prompting.instruction import (
    format_inference_prompt,
    format_prompt,
    format_training_prompt,
)

__all__ = [
    "CanonicalPromptBuilder",
    "EVIDENCE_PLACEHOLDER",
    "PROMPT_TEMPLATE_VERSION",
    "canonical_prompt_template",
    "format_inference_prompt",
    "format_prompt",
    "format_training_prompt",
    "normalize_retrieved_evidence",
]
