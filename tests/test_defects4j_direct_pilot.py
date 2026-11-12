import json
from io import BytesIO
from urllib.request import Request

import pytest

from llm_ontology.benchmarks import defects4j_direct_pilot as pilot
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.retrieval.models import RetrievalMode, RetrievalRequest
from llm_ontology.retrieval.pipeline import VectorRetriever


@pytest.mark.parametrize("think", [None, False, True, "low", "medium", "high"])
def test_think_is_explicit_and_default_unchanged(think):
    requests = []
    def opener(request, **kwargs):
        requests.append(json.loads(request.data))
        return BytesIO(b'{"response":"ok"}')
    provider = OllamaProvider(model_name="model", think=think, opener=opener)
    provider.generate_result("prompt", json_schema={"type": "object"})
    assert requests[0]["format"] == {"type": "object"}
    assert ("think" in requests[0]) == (think is not None)
    if think is not None:
        assert requests[0]["think"] == think


def test_direct_never_touches_store():
    result = VectorRetriever(pilot.ForbiddenStore()).retrieve(
        RetrievalRequest(query="q", mode=RetrievalMode.NO_RAG))
    assert result.documents == []
    assert result.trace.prompt_document_ids == []


def test_dispatch_is_once_even_on_failure(tmp_path, monkeypatch):
    out = tmp_path / "cases/Lang-24/predictions/qwen_base"
    out.mkdir(parents=True)
    calls = []
    def fail(request, **kwargs):
        calls.append(request)
        raise RuntimeError("failed transport")
    monkeypatch.setattr(pilot, "urlopen", fail)
    ledger = pilot.RequestLedger(tmp_path, out)
    request = Request("http://localhost:11434/api/generate", data=b'{"model":"m"}')
    with pytest.raises(RuntimeError, match="failed transport"):
        ledger(request)
    with pytest.raises(FileExistsError):
        ledger(request)
    assert len(calls) == 1
    assert json.loads((out / "dispatch.json").read_text())["request"]["keep_alive"] == 0


def test_seventh_dispatch_never_reaches_server(tmp_path, monkeypatch):
    for i in range(6):
        path = tmp_path / f"cases/{i}/predictions/model/dispatch.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}")
    out = tmp_path / "cases/extra/predictions/model"
    out.mkdir(parents=True)
    def forbidden(*args, **kwargs):
        raise AssertionError("must not dispatch")
    monkeypatch.setattr(pilot, "urlopen", forbidden)
    with pytest.raises(RuntimeError, match="cap exceeded"):
        pilot.RequestLedger(tmp_path, out)(Request("http://localhost:11434/api/generate", data=b'{}'))
