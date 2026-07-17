from __future__ import annotations

from llm_ontology.approaches.contracts import PreparedPrompt, PromptRequest
from llm_ontology.inference.prompting import format_inference_prompt


class DirectApproach:
    name = "direct"

    def prepare_prompt(self, request: PromptRequest) -> PreparedPrompt:
        if request.contexts:
            raise ValueError("The direct approach does not accept retrieved contexts.")
        return PreparedPrompt(
            approach=self.name,
            text=format_inference_prompt(request.instruction, request.input_text),
        )
