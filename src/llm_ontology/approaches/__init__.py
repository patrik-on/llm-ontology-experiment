"""Generation approaches: direct prompting, RAG, and multi-RAG."""

from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest, RetrievedContext
from llm_ontology.approaches.registry import available_approaches, get_approach

__all__ = [
    "PreparedPrompt",
    "PromptRequest",
    "RetrievedContext",
    "available_approaches",
    "get_approach",
]
