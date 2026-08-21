from __future__ import annotations

import hashlib
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

from llm_ontology.retrieval.models import (
    RetrievalHit,
    FusionContribution,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTrace,
)
from llm_ontology.retrieval.reranking import CodeAwareReranker, query_method_name
from llm_ontology.vectorstore.contracts import VectorStore


LOGGER = logging.getLogger(__name__)


class NoOpReranker:
    def rerank(self, query: str, documents: list[RetrievalHit]) -> list[RetrievalHit]:
        return documents


def _rerank(
    strategy: str,
    query: str,
    documents: list[RetrievalHit],
) -> list[RetrievalHit]:
    if strategy == "none":
        return NoOpReranker().rerank(query, documents)
    if strategy == CodeAwareReranker.strategy_name:
        return CodeAwareReranker().rerank(query, documents)
    raise ValueError(f"Unsupported reranking strategy: {strategy!r}")


class VectorRetriever:
    """Shared retrieval pipeline for direct, single RAG and MultiRAG."""

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def _query_candidates(
        self,
        request: RetrievalRequest,
        collection: str,
        where: dict[str, Any],
        candidate_k: int,
    ) -> tuple[list[RetrievalHit], int]:
        dense = self.vector_store.query(
            collection,
            request.query,
            top_k=candidate_k,
            where=where,
        )
        if request.reranking_strategy != CodeAwareReranker.strategy_name:
            return dense, len(dense)

        method_name = query_method_name(request.query)
        if not method_name or "method_name" in request.metadata_filter:
            return _deduplicate_candidates(dense), len(dense)
        method_where = build_chroma_where(
            {**request.metadata_filter, "method_name": method_name},
            request.allowed_splits,
        )
        exact_method = self.vector_store.query(
            collection,
            request.query,
            top_k=candidate_k,
            where=method_where,
        )
        combined = [*dense, *exact_method]
        return _deduplicate_candidates(combined), len(combined)

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

        if request.mode == RetrievalMode.ONTOLOGY_ENHANCED_RAG:
            raise NotImplementedError(
                "Ontology-enhanced retrieval is not implemented."
            )
        if request.mode == RetrievalMode.MULTI_COLLECTION_RAG:
            return self._retrieve_multi(request, started)
        if len(request.collections) != 1:
            raise ValueError(f"{request.mode.value} requires exactly one collection.")

        where = build_chroma_where(request.metadata_filter, request.allowed_splits)
        candidate_k = request.candidate_pool_size or request.top_k
        search_started = perf_counter()
        hits, candidates_before = self._query_candidates(
            request,
            request.collections[0],
            where,
            candidate_k,
        )
        search_ms = (perf_counter() - search_started) * 1000
        rerank_started = perf_counter()
        ranked = _rerank(request.reranking_strategy, request.query, hits)
        rerank_ms = (perf_counter() - rerank_started) * 1000
        top_ranked = ranked[: request.top_k]
        selected, estimated_tokens = fit_context_budget(
            top_ranked,
            request.max_context_tokens,
        )
        total_ms = (perf_counter() - started) * 1000
        trace = RetrievalTrace(
            query=request.query,
            transformed_queries=[request.query],
            selected_collections=request.collections,
            applied_filters=where,
            candidate_documents=ranked,
            retrieved_documents=top_ranked,
            reranking_strategy=(
                request.reranking_strategy
                if request.reranking_strategy != "none"
                else None
            ),
            candidate_pool_size=candidate_k,
            candidates_before_deduplication=candidates_before,
            candidates_after_deduplication=len(ranked),
            prompt_document_ids=[document.document_id for document in selected],
            estimated_context_tokens=estimated_tokens,
            step_latency_ms={"vector_search": search_ms, "reranking": rerank_ms},
            total_latency_ms=total_ms,
        )
        LOGGER.info(
            "Retrieval complete mode=%s collection=%s hits=%d selected=%d latency_ms=%.3f",
            request.mode.value,
            request.collections[0],
            len(ranked),
            len(selected),
            total_ms,
        )
        return RetrievalResult(documents=selected, trace=trace)

    def _retrieve_multi(
        self, request: RetrievalRequest, started: float
    ) -> RetrievalResult:
        if len(request.collections) < 2:
            raise ValueError("multi_collection_rag requires at least two collections.")
        if len(request.collections) != len(set(request.collections)):
            raise ValueError("multi_collection_rag collections must be unique.")
        where = build_chroma_where(request.metadata_filter, request.allowed_splits)
        candidate_k = (
            request.candidate_pool_size
            or request.per_collection_top_k
            or request.top_k
        )

        def query_collection(
            collection: str,
        ) -> tuple[str, list[RetrievalHit], int, float]:
            search_started = perf_counter()
            hits, candidates_before = self._query_candidates(
                request,
                collection,
                where,
                candidate_k,
            )
            return (
                collection,
                hits,
                candidates_before,
                (perf_counter() - search_started) * 1000,
            )

        with ThreadPoolExecutor(
            max_workers=len(request.collections), thread_name_prefix="multirag"
        ) as executor:
            results = list(executor.map(query_collection, request.collections))

        collection_results = {
            collection: hits for collection, hits, _, _ in results
        }
        fusion_started = perf_counter()
        fused, _ = reciprocal_rank_fusion(
            collection_results, rrf_k=request.rrf_k
        )
        fusion_ms = (perf_counter() - fusion_started) * 1000
        rerank_started = perf_counter()
        reranked = _rerank(request.reranking_strategy, request.query, fused)
        rerank_ms = (perf_counter() - rerank_started) * 1000
        globally_ranked = reranked[: request.top_k]
        selected, estimated_tokens = fit_context_budget(
            globally_ranked, request.max_context_tokens
        )
        total_ms = (perf_counter() - started) * 1000
        trace = RetrievalTrace(
            query=request.query,
            transformed_queries=[request.query],
            selected_collections=request.collections,
            applied_filters=where,
            candidate_documents=reranked,
            retrieved_documents=globally_ranked,
            collection_results=collection_results,
            fusion_strategy="rrf",
            rrf_k=request.rrf_k,
            reranking_strategy=(
                request.reranking_strategy
                if request.reranking_strategy != "none"
                else None
            ),
            candidate_pool_size=candidate_k,
            candidates_before_deduplication=sum(
                candidates_before for _, _, candidates_before, _ in results
            ),
            candidates_after_deduplication=len(reranked),
            prompt_document_ids=[document.document_id for document in selected],
            estimated_context_tokens=estimated_tokens,
            step_latency_ms={
                **{
                    f"vector_search:{collection}": latency
                    for collection, _, _, latency in results
                },
                "fusion": fusion_ms,
                "reranking": rerank_ms,
            },
            total_latency_ms=total_ms,
        )
        LOGGER.info(
            "MultiRAG complete collections=%s candidates=%d deduplicated=%d "
            "selected=%d rrf_k=%d latency_ms=%.3f",
            request.collections,
            sum(candidates_before for _, _, candidates_before, _ in results),
            len(fused),
            len(selected),
            request.rrf_k,
            total_ms,
        )
        return RetrievalResult(documents=selected, trace=trace)


def _deduplicate_candidates(documents: list[RetrievalHit]) -> list[RetrievalHit]:
    """Keep the best-ranked representative for equivalent input-side evidence."""

    deduplicated: list[RetrievalHit] = []
    seen_keys: set[str] = set()
    for document in documents:
        keys = _deduplication_keys(document)
        if keys & seen_keys:
            continue
        seen_keys.update(keys)
        deduplicated.append(document)
    return deduplicated


def reciprocal_rank_fusion(
    collection_results: dict[str, list[RetrievalHit]], *, rrf_k: int = 60
) -> tuple[list[RetrievalHit], int]:
    """Fuse collection-local ranks and deduplicate equivalent evidence."""

    if rrf_k < 1:
        raise ValueError("rrf_k must be positive.")
    occurrences = [
        (collection, rank, hit)
        for collection, hits in collection_results.items()
        for rank, hit in enumerate(hits, start=1)
    ]
    parents = list(range(len(occurrences)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    owners: dict[str, int] = {}
    for index, (_, _, hit) in enumerate(occurrences):
        for key in _deduplication_keys(hit):
            previous = owners.setdefault(key, index)
            union(index, previous)

    grouped: dict[int, list[tuple[str, int, RetrievalHit]]] = {}
    for index, occurrence in enumerate(occurrences):
        grouped.setdefault(find(index), []).append(occurrence)

    fused: list[RetrievalHit] = []
    for group in grouped.values():
        representative = min(group, key=lambda item: (item[1], -item[2].score))[2]
        best_by_collection: dict[str, tuple[int, RetrievalHit]] = {}
        for collection, rank, hit in group:
            current = best_by_collection.get(collection)
            if current is None or (rank, -hit.score) < (current[0], -current[1].score):
                best_by_collection[collection] = (rank, hit)
        contributions = [
            FusionContribution(
                collection=collection,
                original_rank=rank,
                original_score=hit.score,
            )
            for collection, (rank, hit) in best_by_collection.items()
        ]
        rrf_score = sum(1.0 / (rrf_k + item.original_rank) for item in contributions)
        fused.append(
            representative.model_copy(
                update={
                    "reranking_score": rrf_score,
                    "fusion_contributions": contributions,
                    "rrf_score": rrf_score,
                    "metadata": {
                        **representative.metadata,
                        "source_collections": sorted(
                            {item.collection for item in contributions}
                        ),
                    },
                }
            )
        )
    fused.sort(
        key=lambda hit: (
            -(hit.rrf_score or 0.0),
            -max(
                (item.original_score for item in hit.fusion_contributions),
                default=hit.score,
            ),
            hit.document_id,
        )
    )
    return [
        hit.model_copy(update={"final_rank": rank})
        for rank, hit in enumerate(fused, start=1)
    ], len(occurrences)


def _deduplication_keys(hit: RetrievalHit) -> set[str]:
    keys = {
        f"document_id:{hit.document_id}",
        f"content:{_content_identity(hit.content)}",
    }
    for field in (
        "content_hash",
        "refactoring_pair_id",
        "test_pair_id",
        "production_method_id",
        "original_method_id",
    ):
        value = str(hit.metadata.get(field, "")).strip()
        if value:
            keys.add(f"{field}:{value}")
    return keys


def _content_identity(content: str) -> str:
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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
