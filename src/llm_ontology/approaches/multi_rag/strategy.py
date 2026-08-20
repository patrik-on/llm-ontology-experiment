from __future__ import annotations

from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest
from llm_ontology.inference.prompting.canonical import CanonicalPromptBuilder


class MultiRagApproach:
    name = "multi_rag"

    def prepare_prompt(self, request: PromptRequest) -> PreparedPrompt:
        return CanonicalPromptBuilder().build_request(request, approach=self.name)
