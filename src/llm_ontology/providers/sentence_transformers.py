from __future__ import annotations

import importlib.metadata
import logging
import random
from time import perf_counter
from typing import Any


LOGGER = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider:
    """Local, revision-pinned Sentence Transformers embedding provider."""

    def __init__(
        self,
        *,
        model_identifier: str,
        model_revision: str,
        remote_code_revision: str | None = None,
        expected_dimension: int,
        device: str = "cpu",
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        max_sequence_length: int | None = None,
        trust_remote_code: bool = False,
        deterministic: bool = True,
    ) -> None:
        if not model_revision.strip():
            raise ValueError("A concrete model revision is required for reproducible embeddings.")
        if expected_dimension < 1:
            raise ValueError("expected_dimension must be positive.")
        if batch_size < 1:
            raise ValueError("batch_size must be positive.")
        self._model_identifier = model_identifier
        self._model_revision = model_revision
        self.remote_code_revision = remote_code_revision
        self._expected_dimension = expected_dimension
        self.device = device
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.max_sequence_length = max_sequence_length
        self.trust_remote_code = trust_remote_code
        self.deterministic = deterministic
        self._model: Any | None = None
        self.model_name = model_identifier
        self.model_version = model_revision
        self.dimension = expected_dimension

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def embedding_dimension(self) -> int:
        return self._expected_dimension

    @property
    def library_versions(self) -> dict[str, str]:
        packages = ("sentence-transformers", "transformers", "torch")
        return {package: importlib.metadata.version(package) for package in packages}

    def embed_documents(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        if not texts:
            return []
        _require_non_empty_texts(texts)
        model = self._load_model()
        selected_batch_size = batch_size or self.batch_size
        started = perf_counter()
        embeddings = model.encode(
            texts,
            batch_size=selected_batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = embeddings.tolist()
        self._validate_dimensions(result)
        LOGGER.info(
            "Embedded documents model=%s revision=%s texts=%d batch_size=%d latency_ms=%.3f",
            self.model_identifier,
            self.model_revision,
            len(texts),
            selected_batch_size,
            (perf_counter() - started) * 1000,
        )
        return result

    def embed_query(self, text: str) -> list[float]:
        _require_non_empty_texts([text])
        return self.embed_documents([text], batch_size=1)[0]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional installation path.
            raise RuntimeError(
                "Sentence Transformers is not installed. Install the rag project extra."
            ) from exc
        if self.deterministic:
            random.seed(0)
            torch.manual_seed(0)
            torch.use_deterministic_algorithms(True, warn_only=True)
        model = SentenceTransformer(
            self.model_identifier,
            revision=self.model_revision,
            device=self.device,
            trust_remote_code=self.trust_remote_code,
            model_kwargs=(
                {"code_revision": self.remote_code_revision}
                if self.remote_code_revision is not None
                else None
            ),
        )
        if self.max_sequence_length is not None:
            model.max_seq_length = self.max_sequence_length
        actual_dimension = int(model.get_sentence_embedding_dimension())
        if actual_dimension != self.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: configured {self.embedding_dimension}, "
                f"model reports {actual_dimension}."
            )
        self._model = model
        return model

    def _validate_dimensions(self, embeddings: list[list[float]]) -> None:
        invalid = [len(vector) for vector in embeddings if len(vector) != self.embedding_dimension]
        if invalid:
            raise ValueError(
                f"Embedding provider returned unexpected dimensions {invalid}; "
                f"expected {self.embedding_dimension}."
            )


def _require_non_empty_texts(texts: list[str]) -> None:
    empty = [index for index, text in enumerate(texts) if not text.strip()]
    if empty:
        raise ValueError(f"Embedding input contains empty text at indexes: {empty}.")
