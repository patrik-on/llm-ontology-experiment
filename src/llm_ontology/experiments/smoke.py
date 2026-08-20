from __future__ import annotations

import argparse
from pathlib import Path

from llm_ontology.experiments.smoke_models import (
    SmokeSelection,
    load_smoke_experiment_config,
)
from llm_ontology.experiments.smoke_runner import SmokeExperimentRunner
from llm_ontology.retrieval.models import RetrievalMode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the resumable handcrafted Direct/RAG/MultiRAG smoke matrix."
    )
    parser.add_argument(
        "--config",
        default="configs/experiments/baseline_v1.yaml",
        help="Smoke experiment YAML configuration.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run preflight and fairness only.")
    parser.add_argument(
        "--task",
        action="append",
        choices=("testing", "refactoring"),
        help="Select one or more tasks.",
    )
    parser.add_argument(
        "--difficulty",
        action="append",
        choices=("easy", "medium", "tricky"),
        help="Select one or more difficulties.",
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=tuple(mode.value for mode in RetrievalMode),
        help="Select one or more retrieval modes.",
    )
    parser.add_argument("--case", action="append", help="Select one or more exact case IDs.")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry only previously failed selected run IDs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Append a new attempt even when a selected run already succeeded.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_smoke_experiment_config(Path(args.config))
    selection = SmokeSelection(
        tasks=tuple(args.task or ()),
        difficulties=tuple(args.difficulty or ()),
        modes=tuple(RetrievalMode(mode) for mode in (args.mode or ())),
        case_ids=tuple(args.case or ()),
        retry_failed=args.retry_failed,
        force=args.force,
    )
    result = SmokeExperimentRunner(config).run(selection, dry_run=args.dry_run)
    print(f"Preflight: {'PASS' if result.preflight_passed else 'FAIL'}")
    print(f"Fairness: {'PASS' if result.fairness_passed else 'FAIL'}")
    print(f"Planned runs: {result.planned_runs}")
    if not args.dry_run:
        print(f"Executed runs: {result.executed_runs}")
        print(f"Skipped runs: {result.skipped_runs}")
        print(f"Successful runs: {result.successful_runs}")
        print(f"Failed runs: {result.failed_runs}")
    print(f"Output: {result.output_dir}")
    return 1 if result.failed_runs else 0


if __name__ == "__main__":
    raise SystemExit(main())
