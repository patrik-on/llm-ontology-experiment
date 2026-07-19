from __future__ import annotations

import argparse

from llm_ontology.core.environment_lock import verify_environment_lock


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the frozen RAG experiment runtime.")
    parser.add_argument(
        "--lock",
        default="configs/environment/rag_baseline_windows_cpu.lock.json",
    )
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--skip-benchmark-toolchain", action="store_true")
    args = parser.parse_args()
    report = verify_environment_lock(
        args.lock,
        check_ollama=not args.skip_ollama,
        check_benchmark_toolchain=not args.skip_benchmark_toolchain,
    )
    print(report.model_dump_json(indent=2))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
