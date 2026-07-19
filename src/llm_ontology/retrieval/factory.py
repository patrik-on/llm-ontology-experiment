from __future__ import annotations

from llm_ontology.core.paths import resolve_path
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.providers.contracts import EmbeddingProvider, LLMProvider
from llm_ontology.providers.mock import DeterministicEmbeddingProvider, MockLLMProvider
from llm_ontology.providers.sentence_transformers import SentenceTransformerEmbeddingProvider
from llm_ontology.retrieval.config import EmbeddingSettings, LLMSettings, RagConfig
from llm_ontology.vectorstore.chroma import ChromaVectorStore, create_chroma_client


def create_embedding_provider(settings: EmbeddingSettings) -> EmbeddingProvider:
    if settings.provider == "deterministic_mock":
        return DeterministicEmbeddingProvider(dimension=settings.dimension)
    if settings.provider == "sentence_transformers":
        if not settings.revision:
            raise ValueError("sentence_transformers provider requires a pinned revision.")
        return SentenceTransformerEmbeddingProvider(
            model_identifier=settings.model,
            model_revision=settings.revision,
            remote_code_revision=settings.remote_code_revision,
            expected_dimension=settings.dimension,
            device=settings.device,
            batch_size=settings.batch_size,
            normalize_embeddings=settings.normalized,
            max_sequence_length=settings.max_sequence_length,
            trust_remote_code=settings.trust_remote_code,
            deterministic=settings.deterministic,
        )
    raise NotImplementedError(
        f"Embedding provider {settings.provider!r} is not implemented in phase 1."
    )


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    if settings.provider == "mock":
        return MockLLMProvider(response=settings.mock_response)
    if settings.provider == "ollama":
        return OllamaProvider(
            model_name=settings.model,
            base_url=settings.base_url,
            temperature=settings.temperature,
            top_p=settings.top_p,
            max_tokens=settings.max_tokens,
            seed=settings.seed,
            timeout_seconds=settings.timeout_seconds,
        )
    raise NotImplementedError(f"LLM provider {settings.provider!r} is not implemented in phase 1.")


def create_vector_store(config: RagConfig) -> ChromaVectorStore:
    if config.vector_store.provider != "chromadb":
        raise NotImplementedError(
            f"Vector store {config.vector_store.provider!r} is not implemented."
        )
    embedding_provider = create_embedding_provider(config.embeddings)
    client = create_chroma_client(resolve_path(config.vector_store.persist_path))
    return ChromaVectorStore(client, embedding_provider)
