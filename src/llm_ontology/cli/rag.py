from __future__ import annotations

import argparse
import json
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
    query_parser.add_argument("--mode", choices=tuple(mode.value for mode in RetrievalMode))
    query_parser.add_argument("--top-k", type=int)
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
        )
        chunker = PassthroughChunker(config.ingestion.pipeline_version)
    else:
        loader = TextDocumentLoader(
            args.input,
            dataset=args.dataset,
            collection=collection,
            split=args.split,
        )
        chunker = StructuredTextChunker(
            config.ingestion.literature_max_chars,
            config.ingestion.pipeline_version,
        )
    pipeline = IndexingPipeline(
        create_vector_store(config),
        allowed_splits=config.ingestion.allowed_splits,
    )
    report = pipeline.run(loader, chunker)
    print(report.model_dump_json(indent=2))
    return 0


def run_query(args: argparse.Namespace, config: RagConfig) -> int:
    mode = RetrievalMode(args.mode) if args.mode else config.retrieval.mode
    collection = (
        config.collections.resolve(args.collection)
        if args.collection
        else _configured_collection(config)
    )
    request = RetrievalRequest(
        query=args.query,
        mode=mode,
        collections=[] if mode == RetrievalMode.NO_RAG else [collection],
        metadata_filter={**config.retrieval.metadata_filter, **parse_filters(args.filter)},
        allowed_splits=config.retrieval.allowed_splits,
        top_k=args.top_k or config.retrieval.top_k,
        max_context_tokens=config.retrieval.max_context_tokens,
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
