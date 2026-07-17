from __future__ import annotations

from llm_ontology.approaches.context_prompt import contextual_prompt, render_grouped_contexts
from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest


class MultiRagApproach:
    name = "multi_rag"

    def prepare_prompt(self, request: PromptRequest) -> PreparedPrompt:
        if not request.contexts:
            raise ValueError("The multi-RAG approach requires contexts from one or more retrieval sources.")
        return PreparedPrompt(
            approach=self.name,
            text=contextual_prompt(
                request.instruction,
                request.input_text,
                render_grouped_contexts(request.contexts),
            ),
            contexts=request.contexts,
        )
