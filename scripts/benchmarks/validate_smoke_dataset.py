"""Validate, compile and leakage-audit the handcrafted smoke dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_ontology.benchmarks.smoke_validation import (
    audit_smoke_leakage,
    refresh_smoke_hashes,
    validate_smoke_dataset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/smoke"))
    parser.add_argument(
        "--refresh-hashes",
        action="store_true",
        help="Recompute the generated hash fields before validation.",
    )
    parser.add_argument(
        "--audit-leakage",
        action="store_true",
        help="Compare smoke fingerprints with the current production retrieval corpora.",
    )
    parser.add_argument(
        "--write-leakage-report",
        action="store_true",
        help="Write the audit to <root>/leakage_report.json (implies --audit-leakage).",
    )
    parser.add_argument(
        "--allow-missing-java",
        action="store_true",
        help="Run structural checks even when a JDK or JUnit artifacts are unavailable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.refresh_hashes:
        refresh_smoke_hashes(args.root)
    summary = validate_smoke_dataset(args.root, require_java=not args.allow_missing_java)
    output: dict[str, object] = {"validation": summary.as_dict()}
    if args.audit_leakage or args.write_leakage_report:
        leakage = audit_smoke_leakage(args.root)
        output["leakage"] = leakage
        if args.write_leakage_report:
            report_path = args.root / "leakage_report.json"
            report_path.write_text(json.dumps(leakage, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
