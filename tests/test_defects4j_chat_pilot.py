import hashlib
from io import BytesIO
import json
from urllib.request import Request

import pytest

from llm_ontology.benchmarks import defects4j_chat_pilot as pilot
from llm_ontology.inference.ollama_client import OllamaProvider


@pytest.mark.parametrize("content", ["", '{"generated_tests":"class Test {}"}'])
def test_chat_separates_content_and_preserves_contract(content):
    captured = []
    raw = {"message": {"role": "assistant", "content": content, "thinking": "private trace"},
           "model": "gpt-oss:20b", "done": True, "done_reason": "stop", "eval_count": 12}
    def fake(request, **kwargs):
        captured.append(request)
        return BytesIO(json.dumps(raw).encode())
    provider = OllamaProvider(model_name="gpt-oss:20b", transport="chat", think="low",
        max_tokens=4096, context_window_tokens=32768, seed=42, opener=fake)
    schema = {"type": "object"}
    result = provider.generate_result("canonical prompt", json_schema=schema)
    request = captured[0]
    payload = json.loads(request.data)
    assert request.full_url == "http://localhost:11434/api/chat"
    assert payload == {"model": "gpt-oss:20b", "messages": [{"role": "user", "content": "canonical prompt"}],
                       "stream": False, "think": "low", "format": schema,
                       "options": {"temperature": 0., "top_p": .9, "num_predict": 4096, "num_ctx": 32768, "seed": 42}}
    assert result.response == content
    assert result.raw == raw
    assert result.transport == "chat"
    assert result.eval_count == 12
    assert result.done_reason == "stop"


@pytest.mark.parametrize("message", [None, {}, {"thinking": "secret"}, {"content": None}])
def test_chat_missing_content_fails_without_disclosing_thinking(message):
    def fake(*args, **kwargs):
        return BytesIO(json.dumps({"message": message}).encode())
    with pytest.raises(RuntimeError, match="message.content") as exc:
        OllamaProvider(model_name="m", transport="chat", opener=fake).generate("p")
    assert "secret" not in str(exc.value)


def test_default_generate_unchanged():
    requests = []
    def fake(request, **kwargs):
        requests.append(request)
        return BytesIO(b'{"response":"ok"}')
    provider = OllamaProvider(model_name="qwen2.5-coder:7b", opener=fake)
    assert provider.generate("p") == "ok"
    assert requests[0].full_url.endswith("/api/generate")
    payload = json.loads(requests[0].data)
    assert payload["prompt"] == "p" and "messages" not in payload and "think" not in payload
    with pytest.raises(ValueError, match="transport"):
        OllamaProvider(model_name="m", transport="invalid")


@pytest.mark.parametrize("fails", [True, False])
def test_single_budget_including_failed_calls(tmp_path, monkeypatch, fails):
    previous = tmp_path / "previous"
    path = previous / "cases/Lang-24/predictions/gptoss20b/dispatch.json"
    path.parent.mkdir(parents=True)
    prior = {"model": "m", "prompt": "p", "keep_alive": 0}
    path.write_text(json.dumps({"request": prior}))
    monkeypatch.setattr(pilot, "PREVIOUS", previous)
    root = tmp_path / "run"
    root.mkdir()
    calls = []
    def fake(request, **kwargs):
        calls.append(request)
        if fails:
            raise RuntimeError("transport failed")
        return BytesIO(b'{"message":{"content":"answer","thinking":"private"}}')
    monkeypatch.setattr(pilot, "urlopen", fake)
    payload = {"model": "m", "messages": [{"role": "user", "content": "p"}]}
    request = Request("http://localhost:11434/api/chat", data=json.dumps(payload).encode())
    ledger = pilot.SingleRequestLedger(root)
    if fails:
        with pytest.raises(RuntimeError, match="transport failed"):
            ledger(request)
    else:
        ledger(request)
        assert (root / "content.txt").read_text() == "answer"
        assert (root / "thinking.private.txt").read_text() == "private"
    with pytest.raises(FileExistsError):
        ledger(request)
    assert len(calls) == 1
    dispatch = json.loads((root / "dispatch.json").read_text())
    assert dispatch["charged_to_budget"] and dispatch["maximum"] == 1
    assert dispatch["request_sha256"] == hashlib.sha256(calls[0].data).hexdigest()
    with pytest.raises(ValueError, match="Only declared"):
        ledger(Request("http://localhost:11434/api/generate", data=b'{}'))


def test_visible_contract_drift_never_dispatches(tmp_path, monkeypatch):
    path = tmp_path / "cases/Lang-24/predictions/gptoss20b/dispatch.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"request": {"prompt": "original", "keep_alive": 0}}))
    monkeypatch.setattr(pilot, "PREVIOUS", tmp_path)
    with pytest.raises(ValueError, match="changed unexpectedly"):
        pilot.SingleRequestLedger(tmp_path)(Request("http://localhost:11434/api/chat",
            data=b'{"messages":[{"role":"user","content":"changed"}]}'))
    assert not (tmp_path / "dispatch.json").exists()
