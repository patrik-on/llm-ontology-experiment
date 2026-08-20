from __future__ import annotations

import json
import logging
import math
import socket
from time import perf_counter
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)


class OllamaEmbeddingProvider:
    """Embedding provider backed by a locally running Ollama server."""

    provider_name = "ollama"
    model_version = "runtime_digest"

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str = "http://localhost:11434",
        expected_dimension: int | None = None,
        batch_size: int = 16,
        timeout_seconds: float = 120.0,
        runtime_environment: str = "unspecified",
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not model_name.strip():
            raise ValueError("Ollama embedding model name must not be blank.")
        if expected_dimension is not None and expected_dimension < 1:
            raise ValueError("expected_dimension must be positive when configured.")
        if batch_size < 1:
            raise ValueError("batch_size must be positive.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        self.model_name = model_name.strip()
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.runtime_environment = runtime_environment
        self._opener = opener
        self._dimension = expected_dimension
        self._model_digest: str | None = None
        self._model_metadata_resolved = False

    @property
    def model_identifier(self) -> str:
        return self.model_name

    @property
    def model_revision(self) -> str:
        return self.resolve_model_digest()

    @property
    def model_digest(self) -> str | None:
        return self._model_digest

    @property
    def embedding_dimension(self) -> int:
        if self._dimension is None:
            self.embed_query("Ollama embedding dimension probe")
        assert self._dimension is not None
        return self._dimension

    @property
    def dimension(self) -> int:
        return self.embedding_dimension

    @property
    def runtime_metadata(self) -> dict[str, str | int]:
        return {
            "embedding_provider": self.provider_name,
            "embedding_model": self.model_identifier,
            "embedding_model_digest": self.resolve_model_digest(),
            "embedding_dimension": self.embedding_dimension,
            "embedding_base_url": self.base_url,
            "ollama_runtime": self.runtime_environment,
        }

    def resolve_model_digest(self) -> str:
        if self._model_metadata_resolved and self._model_digest:
            return self._model_digest
        data = self._request_json("/api/tags", None, method="GET")
        for model in data.get("models", []):
            if not isinstance(model, dict):
                continue
            installed_name = str(model.get("name") or model.get("model") or "")
            if not _same_model_name(installed_name, self.model_name):
                continue
            digest = str(model.get("digest") or "").strip()
            if not digest:
                raise RuntimeError(
                    f"Ollama embedding model {self.model_name!r} has no digest in /api/tags."
                )
            self._model_digest = digest
            self._model_metadata_resolved = True
            LOGGER.info(
                "Resolved Ollama embedding model=%s digest=%s base_url=%s",
                self.model_name,
                digest,
                self.base_url,
            )
            return digest
        raise _missing_model_error(self.model_name)

    def embed_query(self, text: str) -> list[float]:
        _require_non_empty_texts([text])
        return self.embed_documents([text], batch_size=1)[0]

    def embed_documents(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        if not texts:
            return []
        _require_non_empty_texts(texts)
        selected_batch_size = batch_size or self.batch_size
        if selected_batch_size < 1:
            raise ValueError("batch_size must be positive.")
        self.resolve_model_digest()
        started = perf_counter()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), selected_batch_size):
            payload = {
                "model": self.model_name,
                "input": texts[start : start + selected_batch_size],
            }
            data = self._request_json("/api/embed", payload)
            batch_vectors = _parse_embeddings(data)
            expected_count = len(payload["input"])
            if len(batch_vectors) != expected_count:
                raise RuntimeError(
                    "Ollama embedding response count mismatch: "
                    f"expected {expected_count}, received {len(batch_vectors)}."
                )
            self._validate_vectors(batch_vectors)
            vectors.extend(batch_vectors)
        LOGGER.info(
            "Embedded documents provider=ollama model=%s digest=%s dimension=%d "
            "documents=%d batch_size=%d latency_ms=%.3f base_url=%s",
            self.model_name,
            self._model_digest,
            self.embedding_dimension,
            len(texts),
            selected_batch_size,
            (perf_counter() - started) * 1000,
            self.base_url,
        )
        return vectors

    def _validate_vectors(self, vectors: list[list[float]]) -> None:
        if not vectors:
            raise RuntimeError("Ollama returned an empty embeddings list.")
        dimensions = {len(vector) for vector in vectors}
        if 0 in dimensions:
            raise RuntimeError("Ollama returned an empty embedding vector.")
        if len(dimensions) != 1:
            raise RuntimeError(
                f"Ollama returned inconsistent embedding dimensions: {sorted(dimensions)}."
            )
        actual_dimension = dimensions.pop()
        if self._dimension is None:
            self._dimension = actual_dimension
        elif actual_dimension != self._dimension:
            raise RuntimeError(
                "Ollama embedding dimension mismatch: "
                f"expected {self._dimension}, received {actual_dimension}."
            )
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise RuntimeError("Ollama returned a non-finite embedding value.")

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
            detail = _http_error_detail(exc)
            if exc.code == 404 or "not found" in detail.lower():
                raise _missing_model_error(self.model_name) from exc
            raise RuntimeError(
                f"Ollama embedding request failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Ollama embedding service is not reachable at {self.base_url}. "
                "Start Ollama and retry."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama embedding endpoint returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama embedding endpoint returned a non-object JSON payload.")
        error = str(parsed.get("error") or "").strip()
        if error:
            if "not found" in error.lower():
                raise _missing_model_error(self.model_name)
            raise RuntimeError(f"Ollama embedding request failed: {error}")
        return parsed


def _parse_embeddings(data: dict[str, Any]) -> list[list[float]]:
    raw = data.get("embeddings")
    if raw is None and "embedding" in data:
        raw = [data["embedding"]]
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Ollama response did not contain non-empty embeddings.")
    if raw and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in raw):
        raw = [raw]
    vectors: list[list[float]] = []
    for vector in raw:
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("Ollama response contains an invalid or empty embedding vector.")
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in vector):
            raise RuntimeError("Ollama response contains a non-numeric embedding value.")
        vectors.append([float(value) for value in vector])
    return vectors


def _require_non_empty_texts(texts: list[str]) -> None:
    empty = [index for index, text in enumerate(texts) if not isinstance(text, str) or not text.strip()]
    if empty:
        raise ValueError(f"Embedding input contains empty text at indexes: {empty}.")


def _same_model_name(installed: str, requested: str) -> bool:
    def canonical(value: str) -> str:
        return value.removesuffix(":latest")

    return canonical(installed) == canonical(requested)


def _missing_model_error(model_name: str) -> RuntimeError:
    return RuntimeError(
        f"Ollama embedding model {model_name!r} is not installed. "
        f"Run: ollama pull {model_name}"
    )


def _http_error_detail(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return str(parsed.get("error") or raw)
        return raw
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return str(exc.reason)
