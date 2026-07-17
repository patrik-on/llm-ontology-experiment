from __future__ import annotations

from llm_ontology.approaches.context_prompt import contextual_prompt, render_flat_contexts
from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest


class RagApproach:
    name = "rag"

    def prepare_prompt(self, request: PromptRequest) -> PreparedPrompt:
        if not request.contexts:
            raise ValueError("The RAG approach requires at least one retrieved context.")
        return PreparedPrompt(
            approach=self.name,
            text=contextual_prompt(
                request.instruction,
                request.input_text,
                render_flat_contexts(request.contexts),
            ),
            contexts=request.contexts,
        )
