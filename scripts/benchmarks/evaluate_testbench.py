from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.benchmarks.testbench_execution import (
    execute_testbench_plan,
    parse_project_java_homes,
    plan_testbench_record,
    read_prediction_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile and execute generated TestBench JUnit tests with Maven.")
    parser.add_argument("--predictions", required=True, help="JSONL produced by run_benchmark.py with predictions.")
    parser.add_argument("--benchmark-root", default="benchmarks/TestBench-main")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--maven", default="mvn")
    parser.add_argument("--java-home", default=os.getenv("TESTBENCH_JAVA8_HOME"))
    parser.add_argument(
        "--project-java-home",
        action="append",
        default=[],
        metavar="PROJECT=PATH",
        help="Override JAVA_HOME for one project; repeat as needed.",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--repair-package", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        project_java_homes = parse_project_java_homes(args.project_java_home)
    except ValueError as exc:
        parser.error(str(exc))
    java17_home = os.getenv("TESTBENCH_JAVA17_HOME")
    if java17_home and "Java" not in project_java_homes:
        project_java_homes["Java"] = java17_home

    records = read_prediction_jsonl(args.predictions)
    if args.limit is not None:
        records = records[: args.limit]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            try:
                plan = plan_testbench_record(
                    record,
                    benchmark_root=args.benchmark_root,
                    default_java_home=args.java_home,
                    project_java_homes=project_java_homes,
                    repair_package=args.repair_package,
                )
                result = execute_testbench_plan(
                    plan,
                    maven_executable=args.maven,
                    timeout_seconds=args.timeout,
                    dry_run=args.dry_run,
                )
            except Exception as exc:
                result = {"id": record.get("id"), "status": "invalid", "error": str(exc)}
            status = str(result["status"])
            counts[status] = counts.get(status, 0) + 1
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()

    print(f"Evaluated {len(records)} TestBench predictions into {output_path}")
    print(f"Statuses: {counts}")
    if counts.get("invalid"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
