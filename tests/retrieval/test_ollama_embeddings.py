from __future__ import annotations

import json
import os
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from llm_ontology.providers.ollama import OllamaEmbeddingProvider
from llm_ontology.providers.mock import DeterministicEmbeddingProvider
from llm_ontology.retrieval.config import EmbeddingSettings, RagConfig
from llm_ontology.retrieval.factory import create_embedding_provider
from llm_ontology.ui.service import EnvironmentStatusService
from llm_ontology.vectorstore.chroma import ChromaVectorStore
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


class FakeOllama:
    def __init__(self, batches: list[list[list[float]]]) -> None:
        self.batches = list(batches)
        self.requests: list[object] = []

    def __call__(self, request: object, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if request.full_url.endswith("/api/tags"):  # type: ignore[attr-defined]
            return FakeResponse(
                {"models": [{"name": "bge-m3:latest", "digest": "sha256:bge"}]}
            )
        payload = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        assert payload["model"] == "bge-m3"
        assert timeout == 5.0
        return FakeResponse({"embeddings": self.batches.pop(0)})


def _provider(opener: object, *, batch_size: int = 16) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        model_name="bge-m3",
        base_url="http://ollama.test",
        batch_size=batch_size,
        timeout_seconds=5.0,
        opener=opener,  # type: ignore[arg-type]
    )


def test_ollama_embeds_one_text_and_exposes_runtime_metadata() -> None:
    fake = FakeOllama([[[0.1, 0.2, 0.3]]])
    provider = _provider(fake)

    vector = provider.embed_query("public int value() { return 1; }")

    assert vector == pytest.approx([0.1, 0.2, 0.3])
    assert provider.runtime_metadata == {
        "embedding_provider": "ollama",
        "embedding_model": "bge-m3",
        "embedding_model_digest": "sha256:bge",
        "embedding_dimension": 3,
        "embedding_base_url": "http://ollama.test",
        "ollama_runtime": "unspecified",
    }


def test_ollama_batches_documents_and_preserves_order() -> None:
    fake = FakeOllama(
        [
            [[1.0, 0.0], [0.0, 1.0]],
            [[0.5, 0.5]],
        ]
    )
    provider = _provider(fake, batch_size=2)

    vectors = provider.embed_documents(["one", "two", "three"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    embed_requests = [
        request for request in fake.requests if request.full_url.endswith("/api/embed")  # type: ignore[attr-defined]
    ]
    assert len(embed_requests) == 2


def test_ollama_rejects_inconsistent_dimensions() -> None:
    provider = _provider(FakeOllama([[[1.0, 0.0]], [[1.0, 0.0, 0.0]]]), batch_size=1)

    with pytest.raises(RuntimeError, match="dimension mismatch"):
        provider.embed_documents(["one", "two"])


def test_ollama_unavailable_has_actionable_error() -> None:
    def unavailable(*args: object, **kwargs: object) -> FakeResponse:
        raise URLError("connection refused")

    with pytest.raises(RuntimeError, match="not reachable.*http://ollama.test"):
        _provider(unavailable).embed_query("query")


def test_ollama_missing_model_has_pull_command() -> None:
    def missing(request: object, timeout: float) -> FakeResponse:
        if request.full_url.endswith("/api/tags"):  # type: ignore[attr-defined]
            return FakeResponse({"models": []})
        raise AssertionError("embed endpoint must not be called")

    with pytest.raises(RuntimeError, match="ollama pull bge-m3"):
        _provider(missing).embed_query("query")


def test_ollama_parses_legacy_single_embedding_and_rejects_bad_payload() -> None:
    class Responses:
        def __init__(self) -> None:
            self.embed_calls = 0

        def __call__(self, request: object, timeout: float) -> FakeResponse:
            if request.full_url.endswith("/api/tags"):  # type: ignore[attr-defined]
                return FakeResponse(
                    {"models": [{"model": "bge-m3", "digest": "sha256:bge"}]}
                )
            self.embed_calls += 1
            return FakeResponse(
                {"embedding": [1, 2, 3]}
                if self.embed_calls == 1
                else {"embeddings": [[1.0, "bad", 3.0]]}
            )

    provider = _provider(Responses())
    assert provider.embed_query("valid") == [1.0, 2.0, 3.0]
    with pytest.raises(RuntimeError, match="non-numeric"):
        provider.embed_query("invalid")


def test_ollama_http_missing_model_response_is_classified() -> None:
    def missing(*args: object, **kwargs: object) -> FakeResponse:
        raise HTTPError(
            "http://ollama.test/api/tags",
            404,
            "Not Found",
            None,
            BytesIO(b'{"error":"model not found"}'),
        )

    with pytest.raises(RuntimeError, match="not installed"):
        _provider(missing).embed_query("query")


def test_factory_creates_ollama_provider_from_configuration() -> None:
    provider = create_embedding_provider(
        EmbeddingSettings(
            provider="ollama",
            model="configured-model",
            base_url="http://configured:11434",
            dimension=None,
        )
    )

    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.model_identifier == "configured-model"
    assert provider.base_url == "http://configured:11434"


def test_manifest_writes_ollama_identity_and_detects_jina_to_ollama_stale_index(
    tmp_path,
) -> None:
    provider = _provider(FakeOllama([[[0.1, 0.2, 0.3]]]))
    expected = create_collection_manifest(
        collection_name="mixed",
        embedding_provider=provider,
        embedding_normalized=True,
        embedding_template_version="1",
        chunker_name="passthrough",
        chunker_version="rag-v2",
        ingestion_pipeline_version="rag-v2",
        dataset_manifests=["sanity"],
    )
    assert expected.embedding_provider == "ollama"
    assert expected.embedding_model == "bge-m3"
    assert expected.embedding_model_digest == "sha256:bge"
    assert expected.embedding_dimension == 3

    jina = expected.model_copy(
        update={
            "embedding_provider": "sentence_transformers",
            "embedding_model": "jinaai/jina-embeddings-v2-base-code",
            "embedding_revision": "jina-revision",
            "embedding_model_digest": "jina-revision",
            "embedding_dimension": 768,
        }
    )
    store = CollectionManifestStore(tmp_path)
    store.write(jina)

    with pytest.raises(IncompatibleCollectionError, match="embedding_provider"):
        store.require_compatible("mixed", expected)

    with pytest.raises(IncompatibleCollectionError, match="stale embeddings"):
        store.require_embedding_compatible("mixed", provider)


def test_environment_panel_uses_embedding_provider_runtime_metadata(tmp_path) -> None:
    class FakeEmbeddingProvider:
        runtime_metadata = {
            "embedding_provider": "ollama",
            "embedding_model": "bge-m3",
            "embedding_model_digest": "sha256:runtime",
            "embedding_dimension": 1024,
            "embedding_base_url": "http://ollama.test",
        }

    class FakeLLMProvider:
        model_version = "fixture"

    config = RagConfig.model_validate(
        {
            "llm": {"provider": "mock", "model": "fixture"},
            "embeddings": {
                "provider": "ollama",
                "model": "bge-m3",
                "base_url": "http://ollama.test",
            },
            "vector_store": {"persist_path": str(tmp_path / "missing")},
        }
    )
    status = EnvironmentStatusService(
        config,
        embedding_provider_factory=lambda settings: FakeEmbeddingProvider(),
        llm_provider_factory=lambda settings: FakeLLMProvider(),
    ).inspect()

    assert status.embedding_provider == "ollama"
    assert status.embedding_model_digest == "sha256:runtime"
    assert status.embedding_dimension == 1024
    assert status.embedding_status == "Ready"
    assert status.ollama_status == "Unavailable"


def test_persistent_chroma_query_checks_manifest_before_reading_collection() -> None:
    class RejectingManifestStore:
        def require_embedding_compatible(self, collection_name, provider):
            assert collection_name == "mixed"
            assert provider.provider_name == "deterministic_mock"
            raise IncompatibleCollectionError("stale embeddings")

    class ClientThatMustNotBeRead:
        def get_collection(self, **kwargs):
            raise AssertionError("Collection must not be read before compatibility check")

    store = ChromaVectorStore(
        ClientThatMustNotBeRead(),
        DeterministicEmbeddingProvider(),
        manifest_store=RejectingManifestStore(),  # type: ignore[arg-type]
    )

    with pytest.raises(IncompatibleCollectionError, match="stale embeddings"):
        store.query("mixed", "query", top_k=3)


def test_persistent_chroma_add_checks_manifest_before_embedding() -> None:
    class RejectingManifestStore:
        def require_embedding_compatible(self, collection_name, provider):
            raise IncompatibleCollectionError("stale embeddings")

    class ExistingCollection:
        name = "mixed"

    class Client:
        def list_collections(self):
            return [ExistingCollection()]

        def get_or_create_collection(self, **kwargs):
            raise AssertionError(
                "Collection must not be opened before compatibility check"
            )

    store = ChromaVectorStore(
        Client(),
        DeterministicEmbeddingProvider(),
        manifest_store=RejectingManifestStore(),  # type: ignore[arg-type]
    )

    with pytest.raises(IncompatibleCollectionError, match="stale embeddings"):
        store.add("mixed", [])


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_OLLAMA_EMBEDDING_TEST") != "1",
    reason="Opt-in local Ollama integration test.",
)
def test_real_ollama_bge_m3_embedding() -> None:
    provider = OllamaEmbeddingProvider(model_name="bge-m3")
    vectors = provider.embed_documents(
        [
            "Extract Method refactors a long Java method.",
            "A JUnit assertion checks the expected value.",
        ]
    )

    assert len(vectors) == 2
    assert provider.embedding_dimension > 0
    assert provider.model_digest
    assert all(len(vector) == provider.embedding_dimension for vector in vectors)
