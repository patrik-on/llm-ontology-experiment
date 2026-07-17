"""Compatibility imports for the original fine-tuning module path.

New code should import these functions from :mod:`llm_ontology.models`.
"""

from llm_ontology.models.loader import (
    apply_lora,
    build_quantization_config,
    load_base_model,
    load_tokenizer,
)

__all__ = [
    "apply_lora",
    "build_quantization_config",
    "load_base_model",
    "load_tokenizer",
]
