from __future__ import annotations

import logging
import math
from time import perf_counter
from typing import Any

from llm_ontology.retrieval.models import (
    RetrievalHit,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTrace,
)
from llm_ontology.vectorstore.contracts import VectorStore


LOGGER = logging.getLogger(__name__)


class NoOpReranker:
    def rerank(self, query: str, documents: list[RetrievalHit]) -> list[RetrievalHit]:
        return documents


class VectorRetriever:
    """Phase-1 retrieval pipeline for no-RAG, single collection and metadata RAG."""

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        started = perf_counter()
        if request.mode == RetrievalMode.NO_RAG:
            trace = RetrievalTrace(
                query=request.query,
                transformed_queries=[request.query],
                total_latency_ms=(perf_counter() - started) * 1000,
            )
            LOGGER.info("Retrieval bypassed mode=no_rag")
            return RetrievalResult(documents=[], trace=trace)

        if request.mode in {
            RetrievalMode.MULTI_COLLECTION_RAG,
            RetrievalMode.ONTOLOGY_ENHANCED_RAG,
        }:
            raise NotImplementedError(
                f"Retrieval mode {request.mode.value!r} is planned after phase 1 and is not implemented."
            )
        if len(request.collections) != 1:
            raise ValueError(f"{request.mode.value} requires exactly one collection.")

        where = build_chroma_where(request.metadata_filter, request.allowed_splits)
        search_started = perf_counter()
        hits = self.vector_store.query(
            request.collections[0],
            request.query,
            top_k=request.top_k,
            where=where,
        )
        search_ms = (perf_counter() - search_started) * 1000
        selected, estimated_tokens = fit_context_budget(hits, request.max_context_tokens)
        total_ms = (perf_counter() - started) * 1000
        trace = RetrievalTrace(
            query=request.query,
            transformed_queries=[request.query],
            selected_collections=request.collections,
            applied_filters=where,
            retrieved_documents=hits,
            prompt_document_ids=[document.document_id for document in selected],
            estimated_context_tokens=estimated_tokens,
            step_latency_ms={"vector_search": search_ms},
            total_latency_ms=total_ms,
        )
        LOGGER.info(
            "Retrieval complete mode=%s collection=%s hits=%d selected=%d latency_ms=%.3f",
            request.mode.value,
            request.collections[0],
            len(hits),
            len(selected),
            total_ms,
        )
        return RetrievalResult(documents=selected, trace=trace)


def build_chroma_where(
    metadata_filter: dict[str, Any], allowed_splits: list[str]
) -> dict[str, Any]:
    if not allowed_splits:
        raise ValueError("At least one allowed retrieval split is required.")
    requested_split = metadata_filter.get("split")
    if requested_split is not None:
        values = requested_split if isinstance(requested_split, list) else [requested_split]
        if not set(values).issubset(set(allowed_splits)):
            raise ValueError("Metadata filter requests a split outside allowed_splits.")

    conditions: list[dict[str, Any]] = []
    for key, value in metadata_filter.items():
        if key == "split":
            continue
        if isinstance(value, list):
            if not value:
                raise ValueError(f"Metadata filter {key!r} cannot contain an empty list.")
            conditions.append({key: {"$in": value}})
        else:
            conditions.append({key: value})
    conditions.append(
        {"split": allowed_splits[0]}
        if len(allowed_splits) == 1
        else {"split": {"$in": allowed_splits}}
    )
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def fit_context_budget(
    documents: list[RetrievalHit], max_context_tokens: int
) -> tuple[list[RetrievalHit], int]:
    selected: list[RetrievalHit] = []
    used = 0
    for document in documents:
        estimated = max(1, math.ceil(len(document.content) / 4))
        if used + estimated > max_context_tokens:
            continue
        selected.append(document)
        used += estimated
    return selected, used
