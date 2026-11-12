"""Repackage the pinned five official EVAL records, without any model calls.

Run from repository root in WSL; source/reference bodies remain ignored. This
recreates extracted-method controls, not upstream project builds. Snapshot absence
checks from the recorded run must be renewed if training/index content changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tarfile

from llm_ontology.benchmarks.defects4j import require_wsl
from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test import SPECS, prepare_record
from llm_ontology.benchmarks.methods2test_pilot import runtime
from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
from llm_ontology.ingestion.manifest import DatasetManifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    require_wsl()
    validate_evaluation_run_id(args.run_id)
    manifest = DatasetManifest.model_validate_json(Path("configs/datasets/manifests/methods2test_unused_eval_v1.json").read_text())
    manifest.require_source_matches()
    if manifest.allowed_for_indexing or manifest.usage_role.value != "pilot_validation":
        raise ValueError("Invalid evaluation role")
    rows = [json.loads(line) for line in Path(manifest.source_path).read_text().splitlines()]
    archive = Path(manifest.metadata["raw_archive"])
    if file_sha256(archive) != manifest.metadata["raw_archive_sha256"]:
        raise ValueError("Raw official EVAL archive changed")
    root = (Path("artifacts/evaluation/runs") / args.run_id).resolve()
    root.mkdir(parents=True, exist_ok=False)
    deps = json.loads(Path("configs/evaluation/methods2test_assertions_v1.json").read_text())
    for item in deps.values():
        if file_sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Assertion library changed")
    wanted = {r["archive_member"]: r for r in rows}
    found = {}
    with tarfile.open(archive, "r|bz2") as tar:
        for member in tar:
            if member.name not in wanted:
                continue
            pin = wanted[member.name]
            payload = tar.extractfile(member).read()
            import hashlib
            if hashlib.sha256(payload).hexdigest() != pin["rich_member_sha256"]:
                raise ValueError("Raw rich member changed")
            found[pin["id"]] = {"id": pin["id"], "member": member.name, "raw": json.loads(payload)}
            if len(found) == len(rows):
                break
    if len(found) != 5:
        raise ValueError("Incomplete official EVAL selection")
    cases = []
    for pin in rows:
        prepared = prepare_record(found[pin["id"]], SPECS[pin["id"]], root / "cases" / pin["id"], runtime(),
                                  [i["path"] for i in deps.values()])
        if not prepared or prepared["production_sha256"] != pin["production_sha256"] or prepared["reference_sha256"] != pin["reference_sha256"]:
            raise ValueError("Pinned wrapper/reference compile/run identity no longer holds")
        cases.append(prepared)
    write_json(root / "selection.json", {"role": "validation", "split": "official eval", "indexing_allowed": False,
               "ids": [p["id"] for p in cases], "cases": cases, "before_model_outputs": True,
               "reproduction_of": "methods2test-eval-five-v1-20261112", "requires_fresh_snapshot_audit_before_generation": True})
    print("Prepared 5 pinned real EVAL cases; 5 reference tests passed; 0 model calls.")


if __name__ == "__main__":
    main()
