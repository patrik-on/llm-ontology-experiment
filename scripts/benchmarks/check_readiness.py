from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.benchmarks.readiness import check_testbench_readiness, checks_as_json, is_ready


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether TestBench direct-LLM generation and Maven evaluation are ready.")
    parser.add_argument("--benchmark-root", default="benchmarks/TestBench-main")
    parser.add_argument("--backend", choices=("prompt-only", "ollama"), default="ollama")
    parser.add_argument("--model-name", default="qwen2.5-coder:7b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--java-home", default=os.getenv("TESTBENCH_JAVA8_HOME"))
    parser.add_argument("--java17-home", default=os.getenv("TESTBENCH_JAVA17_HOME"))
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    checks = check_testbench_readiness(
        root=args.benchmark_root,
        backend=args.backend,
        model_name=args.model_name,
        base_url=args.base_url,
        java_home=args.java_home,
        java17_home=args.java17_home,
    )
    if args.as_json:
        print(json.dumps(checks_as_json(checks), indent=2))
    else:
        for check in checks:
            print(f"[{check.status.upper():4}] {check.name}: {check.detail}")
        print("READY" if is_ready(checks) else "NOT READY")
    if not is_ready(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
