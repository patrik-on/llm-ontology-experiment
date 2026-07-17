from __future__ import annotations

from collections.abc import Iterable

from llm_ontology.approaches import PreparedPrompt, PromptRequest, RetrievedContext, get_approach


def prepare_prompt(
    approach_name: str,
    *,
    task: str,
    instruction: str,
    input_text: str,
    contexts: Iterable[RetrievedContext] = (),
) -> PreparedPrompt:
    """Prepare a prompt without coupling the caller to a concrete approach."""

    request = PromptRequest(
        task=task,
        instruction=instruction,
        input_text=input_text,
        contexts=tuple(contexts),
    )
    return get_approach(approach_name).prepare_prompt(request)
