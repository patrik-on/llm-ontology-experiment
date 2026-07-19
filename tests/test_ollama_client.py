from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

import llm_ontology.inference.ollama_client as client


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"response":"generated"}'


def test_ollama_request_includes_reproducibility_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    output = client.generate_with_ollama(
        prompt="prompt",
        model_name="model",
        base_url="http://localhost:11434",
        temperature=0.0,
        top_p=0.9,
        max_tokens=512,
        seed=42,
    )

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
    assert output == "generated"
    assert payload["options"]["seed"] == 42
    assert payload["options"]["temperature"] == 0.0


def test_ollama_http_error_is_reported_as_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: object, **kwargs: object) -> FakeResponse:
        raise HTTPError("http://localhost", 500, "boom", None, None)

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        client.generate_with_ollama("p", "m", "http://localhost", 0.0, 0.9, 10)
