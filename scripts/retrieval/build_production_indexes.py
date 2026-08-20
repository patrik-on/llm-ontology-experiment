"""Build leakage-audited production Chroma collections with Ollama embeddings."""

from __future__ import annotations

import argparse
from pathlib import Path

from llm_ontology.core.logging import setup_logging
from llm_ontology.ingestion.production import build_production_indexes
from llm_ontology.retrieval.config import load_rag_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and rebuild equivalent mixed and disjoint production indexes."
    )
    parser.add_argument("--config", default="configs/retrieval/ollama_bge_m3.yaml")
    parser.add_argument(
        "--testing-retrieval-manifest",
        default="configs/datasets/manifests/testing_retrieval.yaml",
    )
    parser.add_argument(
        "--refactoring-retrieval-manifest",
        default="configs/datasets/manifests/refactoring_retrieval.yaml",
    )
    parser.add_argument(
        "--testing-benchmark-manifest",
        default="configs/datasets/manifests/testing_benchmark.yaml",
    )
    parser.add_argument(
        "--refactoring-benchmark-manifest",
        default="configs/datasets/manifests/refactoring_benchmark.yaml",
    )
    parser.add_argument(
        "--report",
        default="artifacts/indexes/ollama_bge_m3_production_report.json",
    )
    args = parser.parse_args()
    setup_logging()
    report = build_production_indexes(
        load_rag_config(args.config),
        testing_retrieval_manifest=args.testing_retrieval_manifest,
        refactoring_retrieval_manifest=args.refactoring_retrieval_manifest,
        testing_benchmark_manifest=args.testing_benchmark_manifest,
        refactoring_benchmark_manifest=args.refactoring_benchmark_manifest,
    )
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
