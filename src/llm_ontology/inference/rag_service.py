from __future__ import annotations

from dataclasses import dataclass

from llm_ontology.approaches import ApproachPromptBuilder, PreparedPrompt, RetrievedContext
from llm_ontology.providers.contracts import LLMProvider
from llm_ontology.retrieval.contracts import Retriever
from llm_ontology.retrieval.models import RetrievalMode, RetrievalRequest, RetrievalResult


@dataclass(frozen=True, slots=True)
class RagGenerationResult:
    response: str
    prepared_prompt: PreparedPrompt
    retrieval: RetrievalResult


class RagGenerationService:
    """Compose retrieval, existing prompt approaches and an LLM provider."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        llm_provider: LLMProvider,
        prompt_builder: ApproachPromptBuilder | None = None,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.prompt_builder = prompt_builder or ApproachPromptBuilder()

    def generate(
        self,
        *,
        task: str,
        instruction: str,
        input_text: str,
        retrieval_request: RetrievalRequest,
    ) -> RagGenerationResult:
        retrieval = self.retriever.retrieve(retrieval_request)
        contexts = tuple(
            RetrievedContext(
                document_id=document.document_id,
                content=document.content,
                source=str(document.metadata.get("source", document.collection)),
                score=document.reranking_score or document.score,
                metadata={**document.metadata, "collection": document.collection},
            )
            for document in retrieval.documents
        )
        approach = "direct" if retrieval_request.mode == RetrievalMode.NO_RAG else "rag"
        prepared = self.prompt_builder.build(
            task=task,
            instruction=instruction,
            input_text=input_text,
            contexts=contexts,
            approach=approach,
        )
        response = self.llm_provider.generate(prepared.text)
        return RagGenerationResult(
            response=response,
            prepared_prompt=prepared,
            retrieval=retrieval,
        )
