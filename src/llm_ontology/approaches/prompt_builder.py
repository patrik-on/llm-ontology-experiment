from __future__ import annotations

from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest, RetrievedContext
from llm_ontology.approaches.registry import get_approach


class ApproachPromptBuilder:
    """Adapter that reuses the repository's existing generation approaches."""

    def build(
        self,
        *,
        task: str,
        instruction: str,
        input_text: str,
        contexts: tuple[RetrievedContext, ...] = (),
        approach: str = "direct",
    ) -> PreparedPrompt:
        request = PromptRequest(
            task=task,
            instruction=instruction,
            input_text=input_text,
            contexts=contexts,
        )
        return get_approach(approach).prepare_prompt(request)
