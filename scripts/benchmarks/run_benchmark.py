from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.benchmarks import available_benchmarks, load_benchmark
from llm_ontology.benchmarks.runner import run_cases
from llm_ontology.inference.ollama_client import generate_with_ollama


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or run direct prompts over a vendored benchmark.")
    parser.add_argument("--benchmark", required=True, choices=available_benchmarks())
    parser.add_argument("--benchmark-root")
    parser.add_argument("--context-level", choices=("source", "simple", "full"), default="source")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--backend", choices=("prompt-only", "ollama"), default="prompt-only")
    parser.add_argument("--model-name", default="qwen2.5-coder:7b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be positive")

    cases = load_benchmark(
        args.benchmark,
        root=args.benchmark_root,
        context_level=args.context_level,
    )[: args.limit]
    generator = None
    if args.backend == "ollama":
        generator = lambda prompt: generate_with_ollama(
            prompt=prompt,
            model_name=args.model_name,
            base_url=args.base_url,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            seed=args.seed,
        )

    results = run_cases(cases, generator=generator)
    generation = {
        "backend": args.backend,
        "model": args.model_name if args.backend == "ollama" else None,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for result in results:
            result["generation"] = generation
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"Wrote {len(results)} {args.benchmark}/direct records using backend={args.backend} to {output_path}")


if __name__ == "__main__":
    main()
