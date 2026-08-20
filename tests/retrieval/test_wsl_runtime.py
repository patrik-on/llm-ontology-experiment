from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.providers.ollama import OllamaEmbeddingProvider
from llm_ontology.providers.sentence_transformers import (
    SentenceTransformerEmbeddingProvider,
)
from llm_ontology.retrieval.config import EmbeddingSettings, RagConfig, load_rag_config
from llm_ontology.retrieval.factory import create_embedding_provider
from llm_ontology.ui.app import COLLECTION_HEADERS, _render_environment
from llm_ontology.ui.service import EnvironmentStatusService
from llm_ontology.vectorstore.manifest import (
    CollectionManifestStore,
    IncompatibleCollectionError,
    create_collection_manifest,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_current_baseline_config_is_wsl_ollama_only() -> None:
    config = load_rag_config("configs/retrieval/ollama_bge_m3.yaml")

    assert config.runtime.environment == "wsl"
    assert config.runtime.status == "current"
    assert config.runtime.ollama_base_url == "http://localhost:11434"
    assert config.embeddings.provider == "ollama"
    assert config.embeddings.model == "bge-m3"
    assert config.embeddings.dimension == 1024
    assert config.embeddings.ollama_runtime == "wsl"
    assert config.llm.provider == "ollama"
    assert config.llm.model == "qwen2.5-coder:7b"


def test_wsl_config_rejects_host_ip_or_fallback_url() -> None:
    with pytest.raises(ValueError, match="exactly http://localhost:11434"):
        RagConfig.model_validate(
            {
                "runtime": {
                    "environment": "wsl",
                    "status": "current",
                    "ollama_base_url": "http://172.20.0.1:11434",
                }
            }
        )


def test_generation_model_digest_is_resolved_from_ollama_tags() -> None:
    def opener(request: object, timeout: float) -> FakeResponse:
        assert request.full_url == "http://localhost:11434/api/tags"  # type: ignore[attr-defined]
        return FakeResponse(
            {
                "models": [
                    {
                        "name": "qwen2.5-coder:7b",
                        "digest": "sha256:qwen-runtime",
                    }
                ]
            }
        )

    provider = OllamaProvider(model_name="qwen2.5-coder:7b", opener=opener)

    assert provider.resolve_model_digest() == "sha256:qwen-runtime"
    assert provider.provider_name == "ollama"


def test_environment_status_reports_ready_wsl_runtime(tmp_path: Path) -> None:
    class FakeEmbeddingProvider:
        runtime_metadata = {
            "embedding_provider": "ollama",
            "embedding_model": "bge-m3",
            "embedding_model_digest": "sha256:bge-runtime",
            "embedding_dimension": 1024,
            "embedding_base_url": "http://localhost:11434",
            "ollama_runtime": "wsl",
        }

    class FakeGenerationProvider:
        provider_name = "ollama"

        def resolve_model_digest(self) -> str:
            return "sha256:qwen-runtime"

    config = RagConfig.model_validate(
        {
            "runtime": {"environment": "wsl", "status": "current"},
            "embeddings": {
                "provider": "ollama",
                "model": "bge-m3",
                "dimension": 1024,
            },
            "llm": {"provider": "ollama", "model": "qwen2.5-coder:7b"},
            "vector_store": {"persist_path": str(tmp_path / "new-index")},
        }
    )
    status = EnvironmentStatusService(
        config,
        runtime_probe=lambda: ("WSL/Linux (fixture)", True),
        dependency_probe=lambda: {
            "pydantic": "available",
            "pyyaml": "available",
            "chromadb": "available",
        },
        embedding_provider_factory=lambda settings: FakeEmbeddingProvider(),
        llm_provider_factory=lambda settings: FakeGenerationProvider(),
    ).inspect()

    assert status.status == "READY"
    assert status.runtime_environment == "wsl"
    assert status.ollama_status == "Ready"
    assert status.embedding_model_digest == "sha256:bge-runtime"
    assert status.embedding_dimension == 1024
    assert status.generation_provider == "ollama"
    assert status.generation_model_digest == "sha256:qwen-runtime"
    assert status.chroma_status == "not_initialized"
    assert "ollama_runtime" in COLLECTION_HEADERS
    panel, collections = _render_environment(status)
    assert panel["runtime_os"] == "WSL/Linux (fixture)"
    assert panel["ollama_base_url"] == "http://localhost:11434"
    assert panel["generation_model"] == "qwen2.5-coder:7b"
    assert collections == []


def test_manifest_runtime_or_digest_mismatch_is_stale(tmp_path: Path) -> None:
    provider = OllamaEmbeddingProvider(
        model_name="bge-m3",
        expected_dimension=1024,
        runtime_environment="wsl",
        opener=lambda request, timeout: FakeResponse(
            {"models": [{"name": "bge-m3:latest", "digest": "sha256:current"}]}
        ),
    )
    manifest = create_collection_manifest(
        collection_name="mixed",
        embedding_provider=provider,
        embedding_normalized=True,
        embedding_template_version="1",
        chunker_name="fixture",
        chunker_version="1",
        ingestion_pipeline_version="rag-v2",
        dataset_manifests=["fixture"],
    )
    store = CollectionManifestStore(tmp_path)
    store.write(
        manifest.model_copy(
            update={
                "ollama_runtime": "legacy_windows",
                "embedding_model_digest": "sha256:old",
            }
        )
    )

    with pytest.raises(IncompatibleCollectionError, match="stale embeddings"):
        store.require_embedding_compatible("mixed", provider)


def test_jina_and_ollama_embedding_providers_remain_selectable() -> None:
    jina = create_embedding_provider(
        EmbeddingSettings(
            provider="sentence_transformers",
            model="jinaai/jina-embeddings-v2-base-code",
            revision="fixture-revision",
            dimension=768,
        )
    )
    ollama = create_embedding_provider(
        EmbeddingSettings(provider="ollama", model="bge-m3", dimension=1024)
    )

    assert isinstance(jina, SentenceTransformerEmbeddingProvider)
    assert isinstance(ollama, OllamaEmbeddingProvider)
