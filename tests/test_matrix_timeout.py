import pytest
from llm_ontology.benchmarks import evaluation_generation as generation
from llm_ontology.benchmarks import matrix_support as shared
from llm_ontology.retrieval.config import load_rag_config


class CapturedProvider(Exception):
    pass


def test_rag_actual_provider_timeout_preserves_embedding_timeout(tmp_path, monkeypatch):
    config = shared.runtime()
    rag = load_rag_config(config.retrieval_config)
    assert config.generation_timeout_seconds == 1800
    assert rag.embeddings.timeout_seconds == 120
    assert rag.llm.timeout_seconds == 120  # shared config untouched
    (tmp_path / "chroma.sqlite3").touch()
    rag = rag.model_copy(update={"vector_store": rag.vector_store.model_copy(update={"persist_path": str(tmp_path)})})
    monkeypatch.setattr(generation, "load_rag_config", lambda _: rag)
    monkeypatch.setattr(generation, "hf_identity", lambda *a, **kw: {"model": {"model_path": str(tmp_path)}})
    monkeypatch.setattr(generation, "file_sha256", lambda _: "digest")
    def capture(llm):
        assert llm.timeout_seconds == 1800
        assert llm.max_tokens == config.max_new_tokens
        raise CapturedProvider
    monkeypatch.setattr(generation, "create_llm_provider", capture)
    with pytest.raises(CapturedProvider):
        generation.generate_rag(config, None, tmp_path, "rag_single", {})


def test_direct_actual_provider_uses_same_timeout(tmp_path, monkeypatch):
    config = shared.runtime()
    monkeypatch.setattr(shared.direct, "counter", lambda: None)
    def capture(**kwargs):
        assert kwargs["timeout_seconds"] == config.generation_timeout_seconds == 1800
        raise CapturedProvider
    monkeypatch.setattr(shared, "OllamaProvider", capture)
    with pytest.raises(CapturedProvider):
        shared._generate_direct(config, None, tmp_path, None)
