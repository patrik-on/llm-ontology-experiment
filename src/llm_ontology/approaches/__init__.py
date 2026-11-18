"""Generation approaches: direct prompting, RAG, and multi-RAG."""

from llm_ontology.approaches.contracts import PreparedPrompt, PromptBuilder, PromptRequest, RetrievedContext


def __getattr__(name):
    # canonical prompting imports lightweight approach contracts/context rendering.
    # Eagerly importing the builders here would recurse into canonical prompting.
    if name == "ApproachPromptBuilder":
        from llm_ontology.approaches.prompt_builder import ApproachPromptBuilder
        return ApproachPromptBuilder
    if name in {"available_approaches", "get_approach"}:
        from llm_ontology.approaches import registry
        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "PreparedPrompt",
    "PromptBuilder",
    "PromptRequest",
    "RetrievedContext",
    "ApproachPromptBuilder",
    "available_approaches",
    "get_approach",
]
