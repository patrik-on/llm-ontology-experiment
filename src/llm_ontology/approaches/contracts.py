from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """One auditable context item supplied by a retrieval layer."""

    document_id: str
    content: str
    source: str = ""
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromptRequest:
    task: str
    instruction: str
    input_text: str
    contexts: tuple[RetrievedContext, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedPrompt:
    approach: str
    text: str
    contexts: tuple[RetrievedContext, ...] = ()


class GenerationApproach(Protocol):
    name: str

    def prepare_prompt(self, request: PromptRequest) -> PreparedPrompt:
        """Render an inference prompt from a request and optional contexts."""


class PromptBuilder(Protocol):
    def build(
        self,
        *,
        task: str,
        instruction: str,
        input_text: str,
        contexts: tuple[RetrievedContext, ...] = (),
        approach: str = "direct",
    ) -> PreparedPrompt:
        """Build a prompt independently from retrieval and LLM providers."""
