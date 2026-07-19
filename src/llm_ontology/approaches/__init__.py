"""Generation approaches: direct prompting, RAG, and multi-RAG."""

from llm_ontology.approaches.contracts import PreparedPrompt, PromptBuilder, PromptRequest, RetrievedContext
from llm_ontology.approaches.prompt_builder import ApproachPromptBuilder
from llm_ontology.approaches.registry import available_approaches, get_approach

__all__ = [
    "PreparedPrompt",
    "PromptBuilder",
    "PromptRequest",
    "RetrievedContext",
    "ApproachPromptBuilder",
    "available_approaches",
    "get_approach",
]
