from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_ontology.core.logging import setup_logging
from llm_ontology.ingestion import (
    IndexingPipeline,
    NormalizedJsonlLoader,
    PassthroughChunker,
    StructuredTextChunker,
    TextDocumentLoader,
)
from llm_ontology.retrieval.config import RagConfig, load_rag_config
from llm_ontology.retrieval.factory import create_vector_store
from llm_ontology.retrieval.models import RetrievalMode, RetrievalRequest
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.query import build_retrieval_query
from llm_ontology.vectorstore.manifest import (
    IncompatibleCollectionError,
    create_collection_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index and query the phase-1 ChromaDB RAG store.")
    parser.add_argument("--config", default="configs/retrieval/base.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index a normalized dataset or literature file.")
    index_parser.add_argument("--input", required=True)
    index_parser.add_argument("--loader", choices=("dataset", "text"), required=True)
    index_parser.add_argument("--dataset", required=True)
    index_parser.add_argument("--collection", required=True, help="Logical collection name from config.")
    index_parser.add_argument("--split", default="train")

    query_parser = subparsers.add_parser("query", help="Run vector retrieval and print its trace.")
    query_parser.add_argument("--query", required=True)
    query_parser.add_argument("--collection", help="Logical collection name from config.")
    query_parser.add_argument(
        "--collections",
        nargs="+",
        help="Logical collection names for MultiRAG (default: tests refactor).",
    )
    query_parser.add_argument("--mode", choices=tuple(mode.value for mode in RetrievalMode))
    query_parser.add_argument("--top-k", type=int)
    query_parser.add_argument("--task", choices=("testing", "refactoring"))
    query_parser.add_argument("--class-name", default="")
    query_parser.add_argument("--focal-method", default="")
    query_parser.add_argument("--requirements", default="")
    query_parser.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE")
    return parser


def run_index(args: argparse.Namespace, config: RagConfig) -> int:
    collection = config.collections.resolve(args.collection)
    if args.loader == "dataset":
        loader = NormalizedJsonlLoader(
            args.input,
            dataset=args.dataset,
            collection=collection,
            split=args.split,
            embedding_template_version=config.ingestion.embedding_template_version,
        )
        chunker = PassthroughChunker(config.ingestion.pipeline_version)
    else:
        loader = TextDocumentLoader(
            args.input,
            dataset=args.dataset,
            collection=collection,
            split=args.split,
            embedding_template_version=config.ingestion.embedding_template_version,
        )
        chunker = StructuredTextChunker(
            config.ingestion.literature_max_chars,
            config.ingestion.pipeline_version,
        )
    vector_store = create_vector_store(config)
    pipeline = IndexingPipeline(
        vector_store,
        allowed_splits=config.ingestion.allowed_splits,
    )
    report = pipeline.run(loader, chunker)
    manifest_store = vector_store.manifest_store
    if manifest_store is not None:
        try:
            previous = manifest_store.read(collection)
        except IncompatibleCollectionError:
            previous = None
        dataset_manifests = sorted(
            {
                *(previous.dataset_manifests if previous else []),
                args.dataset,
            }
        )
        manifest_store.write(
            create_collection_manifest(
                collection_name=collection,
                embedding_provider=vector_store.embedding_provider,
                embedding_normalized=config.embeddings.normalized,
                embedding_template_version=config.ingestion.embedding_template_version,
                chunker_name=(
                    "passthrough"
                    if args.loader == "dataset"
                    else "structured_text"
                ),
                chunker_version=config.ingestion.pipeline_version,
                ingestion_pipeline_version=config.ingestion.pipeline_version,
                dataset_manifests=dataset_manifests,
                document_count=(previous.document_count if previous else 0)
                + report.indexed,
            )
        )
    print(report.model_dump_json(indent=2))
    return 0


def run_query(args: argparse.Namespace, config: RagConfig) -> int:
    mode = RetrievalMode(args.mode) if args.mode else config.retrieval.mode
    metadata_filter = {
        **config.retrieval.metadata_filter,
        **parse_filters(args.filter),
    }
    if mode == RetrievalMode.MULTI_COLLECTION_RAG:
        if args.collection:
            raise ValueError("Use --collections, not --collection, for MultiRAG.")
        logical_collections = getattr(args, "collections", None) or [
            "tests",
            "refactor",
        ]
        collections = [
            config.collections.resolve(name) for name in logical_collections
        ]
    elif mode == RetrievalMode.NO_RAG:
        collections = []
    else:
        collections = [
            config.collections.resolve(args.collection)
            if args.collection
            else _configured_collection(config)
        ]
    task = args.task or str(metadata_filter.get("task", "")).strip()
    if config.retrieval.query_strategy == "task_aware_v1" and not task:
        raise ValueError("task_aware_v1 query requires --task or a task metadata filter.")
    query = build_retrieval_query(
        strategy=config.retrieval.query_strategy,
        task=task or "testing",
        input_text=args.query,
        requirements=args.requirements,
        structured_identity={
            "class_name": args.class_name,
            "focal_method": args.focal_method,
        },
    )
    request = RetrievalRequest(
        query=query,
        mode=mode,
        collections=collections,
        metadata_filter=metadata_filter,
        allowed_splits=config.retrieval.allowed_splits,
        top_k=args.top_k or config.retrieval.top_k,
        max_context_tokens=config.retrieval.max_context_tokens,
        rrf_k=config.retrieval.rrf_k,
        per_collection_top_k=config.retrieval.per_collection_top_k,
        candidate_pool_size=config.retrieval.candidate_pool_size,
        reranking_strategy=config.retrieval.reranking_strategy,
    )
    result = VectorRetriever(create_vector_store(config)).retrieve(request)
    print(result.model_dump_json(indent=2))
    return 0


def _configured_collection(config: RagConfig) -> str:
    if len(config.retrieval.collections) != 1:
        raise ValueError("Phase-1 query needs exactly one configured logical collection.")
    return config.collections.resolve(config.retrieval.collections[0])


def parse_filters(values: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not separator or not key.strip() or not raw.strip():
            raise ValueError(f"Invalid metadata filter {value!r}; expected KEY=VALUE.")
        parsed[key.strip()] = _parse_scalar(raw.strip())
    return parsed


def _parse_scalar(value: str) -> str | int | float | bool:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    config = load_rag_config(Path(args.config))
    if args.command == "index":
        return run_index(args, config)
    return run_query(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
