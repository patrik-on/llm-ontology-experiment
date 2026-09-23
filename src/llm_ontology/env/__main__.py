from __future__ import annotations

import argparse
from pathlib import Path

from llm_ontology.core.paths import resolve_path
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.ui.service import EnvironmentStatusService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the shared WSL-only experiment runtime."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Check WSL, Ollama, models and Chroma.")
    check.add_argument(
        "--config",
        type=Path,
        default=Path("configs/retrieval/ollama_bge_m3.yaml"),
    )
    check.add_argument("--json", action="store_true", help="Print the complete JSON status.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_rag_config(resolve_path(args.config))
    status = EnvironmentStatusService(config).inspect()
    if args.json:
        print(status.model_dump_json(indent=2))
    else:
        print(f"Environment: {status.runtime_os}")
        print(f"Ollama: {status.ollama_status} ({status.ollama_base_url})")
        print(
            "Embedding: "
            f"{status.embedding_provider}/{status.embedding_model} "
            f"digest={status.embedding_model_digest} dim={status.embedding_dimension}"
        )
        print(
            "Generation: "
            f"{status.generation_provider}/{status.generation_model} "
            f"digest={status.generation_model_digest}"
        )
        print(f"Chroma: {status.chroma_status} ({status.chroma_path})")
        print(f"Python: {status.python_version}")
        if status.collections:
            print("Collections: " + ", ".join(item.name for item in status.collections))
        else:
            print("Collections: none")
        for error in status.errors:
            print(f"ERROR: {error}")
        print(f"Status: {status.status}")
    return 0 if status.status == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
