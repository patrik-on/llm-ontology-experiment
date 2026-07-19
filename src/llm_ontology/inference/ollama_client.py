from __future__ import annotations

import json
import socket
from time import perf_counter
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


class OllamaGenerationResult(BaseModel):
    response: str
    model: str
    model_digest: str | None = None
    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_count: int | None = None
    eval_duration_ns: int | None = None
    client_latency_ms: float
    raw: dict[str, Any] = Field(default_factory=dict)


class OllamaProvider:
    """Reproducible Ollama generation boundary with optional JSON schema output."""

    model_version = "runtime_digest"

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
        seed: int | None = 42,
        timeout_seconds: float = 120.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.seed = seed
        self.timeout_seconds = timeout_seconds
        self._opener = opener
        self.model_digest: str | None = None

    def generate(self, prompt: str) -> str:
        return self.generate_result(prompt).response

    def generate_result(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
    ) -> OllamaGenerationResult:
        if not prompt.strip():
            raise ValueError("Ollama prompt must not be blank.")
        options: dict[str, float | int] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "num_predict": self.max_tokens,
        }
        if self.seed is not None:
            options["seed"] = self.seed
        payload: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if json_schema is not None:
            payload["format"] = json_schema
        started = perf_counter()
        data = self._request_json("/api/generate", payload)
        latency_ms = (perf_counter() - started) * 1000
        if "response" not in data:
            raise RuntimeError(f"Ollama response did not contain a 'response' field: {data}")
        return OllamaGenerationResult(
            response=str(data["response"]),
            model=str(data.get("model", self.model_name)),
            model_digest=self.model_digest,
            total_duration_ns=_optional_int(data.get("total_duration")),
            load_duration_ns=_optional_int(data.get("load_duration")),
            prompt_eval_count=_optional_int(data.get("prompt_eval_count")),
            prompt_eval_duration_ns=_optional_int(data.get("prompt_eval_duration")),
            eval_count=_optional_int(data.get("eval_count")),
            eval_duration_ns=_optional_int(data.get("eval_duration")),
            client_latency_ms=latency_ms,
            raw=data,
        )

    def resolve_model_digest(self) -> str:
        data = self._request_json("/api/tags", None, method="GET")
        for model in data.get("models", []):
            if model.get("name") == self.model_name or model.get("model") == self.model_name:
                digest = str(model.get("digest", "")).strip()
                if not digest:
                    break
                self.model_digest = digest
                return digest
        raise RuntimeError(f"Ollama model {self.model_name!r} is not installed or has no digest.")

    def _request_json(
        self,
        path: str,
        payload: dict[str, Any] | None,
        *,
        method: str = "POST",
    ) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Ollama request failed with HTTP {exc.code}: {exc.reason}"
            ) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self.base_url}. "
                "Start Ollama and ensure the model is available."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama returned a non-object JSON payload.")
        return parsed


def generate_with_ollama(
    prompt: str,
    model_name: str,
    base_url: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    seed: int | None = None,
) -> str:
    provider = OllamaProvider(
        model_name=model_name,
        base_url=base_url,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        seed=seed,
        opener=urlopen,
    )
    return provider.generate(prompt)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
