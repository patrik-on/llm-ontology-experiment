"""Session-owned sequential pipeline. No retries/repairs or partial cohort dispatch."""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import traceback
from llm_ontology.benchmarks.defects4j_execution import write_json
from llm_ontology.benchmarks.methods2test_batch import ARMS, freeze, generate, verify, read
from llm_ontology.benchmarks.methods2test_hundred_evaluation import run as evaluate
from llm_ontology.benchmarks.methods2test_hundred_report import finalize


def publish_manifest(root):
    import json
    from llm_ontology.ingestion.manifest import (
        create_dataset_manifest,
        UsageRole,
        SplitGroupingPolicy,
        GroupLevel,
    )
    from llm_ontology.benchmarks.defects4j_execution import file_sha256

    selected = read(root / "selection.json")
    from llm_ontology.benchmarks.methods2test_selection import infer_spec, general_wrap_record

    for ident in selected["ids"]:
        cr = root / "cases" / ident
        record = read(cr / "raw-private.json")
        spec = infer_spec(record["raw"])
        production, reference, _ = general_wrap_record(record, spec)
        if (
            production != read(cr / "case.json")["input_text"]
            or reference != (cr / "reference-private.java").read_text()
        ):
            raise ValueError(
                "Latest safety/import policy requires candidate revalidation: " + ident
            )
    path = Path("data/validation/methods2test_unused_eval_hundred_v1/selection.jsonl")
    rows = []
    for p in selected["cases"]:
        row = {
            k: p[k]
            for k in [
                "id",
                "repository",
                "project_id",
                "archive_member",
                "archive_member_sha256",
                "focal_class",
                "focal_method",
                "production_sha256",
                "reference_sha256",
                "source_class_path",
                "source_test_path",
            ]
        }
        row.update(p["selection_audit"])
        rows.append(row)
    content = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != content:
        raise ValueError("published_selection_changed")
    path.write_text(content)
    manifest = create_dataset_manifest(
        path,
        dataset_name="methods2test_unused_eval_hundred",
        dataset_version="v1-20261112",
        source_split="eval",
        usage_role=UsageRole.PILOT_VALIDATION,
        allowed_for_indexing=False,
        sample_count=100,
        case_count=100,
        tasks=["testing"],
        metadata={
            "raw_archive": "data/raw/methods2test/dataset/eval.tar.bz2",
            "raw_archive_sha256": file_sha256(Path("data/raw/methods2test/dataset/eval.tar.bz2")),
            "gold_not_committed": True,
            "original_project_build": False,
            "official_test_reserved": True,
        },
        grouping_policy=SplitGroupingPolicy(
            primary_group_level=GroupLevel.PROJECT,
            group_fields=["repository", "project_id"],
            related_case_fields=["id"],
            audit_report_path=str(root / "leakage_audit.json"),
        ),
    )
    manifest.require_source_matches()
    target = Path("configs/datasets/manifests/methods2test_unused_eval_hundred_v1.json")
    if target.exists():
        from llm_ontology.ingestion.manifest import read_dataset_manifest

        if read_dataset_manifest(target).manifest_id != manifest.manifest_id:
            raise ValueError("published_manifest_changed")
    else:
        write_json(target, manifest.model_dump(mode="json"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id

    validate_evaluation_run_id(a.run_id)
    root = (Path("artifacts/evaluation/runs") / a.run_id).resolve()

    def state(phase, **kwargs):
        payload = {"phase": phase, "updated_at": datetime.now(timezone.utc).isoformat(), **kwargs}
        write_json(root / "pipeline.json", payload)
        with (root / "pipeline.log").open("a") as f:
            f.write(str(payload) + "\n")
        print("PIPELINE", payload, flush=True)

    try:
        if len(read(root / "selection.json")["ids"]) != 100:
            raise ValueError("complete100_required")
        publish_manifest(root)
        state("freeze")
        if not (root / "freeze.json").exists():
            freeze(root)
        verify(root)
        for arm in ARMS:
            state("generation", arm=arm)
            generate(root, arm, first_cell_callback=evaluate)
            # Evaluate stored immutable sources between arms, never request repair.
            state("offline_evaluation", arm=arm)
            evaluate(root)
        state("final_verification")
        result = finalize(root)
        state("complete", actual_calls=result["actual_calls"])
    except Exception as exc:
        state("blocked", error=str(exc), traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
