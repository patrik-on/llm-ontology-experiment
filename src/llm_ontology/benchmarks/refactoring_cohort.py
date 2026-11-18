"""Single fixed mixed-source cohort with deterministic stratified subsets."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json

from llm_ontology.benchmarks import refactoring_execution as ex
from llm_ontology.benchmarks.refactoring_candidates import QUOTAS
from llm_ontology.benchmarks import refactoring_structural as structural


def load(repo, plan):
    path = repo / plan["cohort_manifest"]
    if not path.is_file():
        raise ValueError("Mixed cohort is not released: run --prepare-pool; inspect quota deficits. No model calls allowed.")
    manifest = json.loads(path.read_text())
    cases = manifest["cases"]
    counts = Counter((c["source"], c["operation"]) for c in cases)
    if len(cases) != 100 or len({c["id"] for c in cases}) != 100:
        raise ValueError("Exactly 100 unique accepted tasks required")
    for source, quotas in QUOTAS.items():
        if source == "swe":
            if sum(c["source"] == source for c in cases) != 5:
                raise ValueError("SWE quota mismatch")
        elif any(counts[source, op] != n for op, n in quotas.items()):
            raise ValueError("Source/type quota mismatch: " + source)
    for path, digest in manifest["files"].items():
        if ex.file_sha256(repo / path) != digest:
            raise ValueError("Cohort evidence changed: " + path)
    return manifest


def subset(cases, count="all", source=None, operation=None):
    groups = defaultdict(list)
    for case in cases:
        if (source is None or case["source"] == source) and (operation is None or case["operation"] == operation):
            groups[case["source"], case["operation"]].append(case)
    # Round-robin strata; stable SHA-ID order; same sample for every model arm.
    for group in groups.values():
        group.sort(key=lambda c: c["id"])
    result = []
    while any(groups.values()):
        for key in sorted(groups):
            if groups[key]:
                result.append(groups[key].pop(0))
    if count != "all" and len(result) < count:
        raise ValueError(f"Requested {count} tasks, only {len(result)} match filters")
    return result if count == "all" else result[:count]


def structural_qa(case, reference, output, tool, validate):
    sizes = validate(case, reference)
    result = structural.evaluate(case, reference, output / "reference", tool)
    noop = structural.evaluate(case, case["before"], output / "noop", tool)
    syntax = structural.evaluate(case, "not Java!", output / "syntax", tool)
    wrong_case = deepcopy(case)
    wrong_case["target_event"]["left"][0]["codeElement"] = "__wrong_target_control__"
    wrong = structural.evaluate(wrong_case, reference, output / "wrong-target", tool)
    checks = {"reference_accepted": result["structural_success"], "noop_rejected": noop["status"] == "no_op",
              "syntax_rejected": syntax["status"] == "invalid_java", "wrong_target_rejected": not wrong["structural_success"]}
    qa = {"passed": all(checks.values()), "checks": checks, "expected_tests": None, "model_calls": 0,
          "prompt_size": sizes}
    ex.write(output / "qa.json", qa)
    return qa


def prepare_selection(repo, root, plan, validate):
    manifest = load(repo, plan)
    cases = subset(manifest["cases"], plan["cases"], plan.get("source_filter"), plan.get("operation_filter"))
    for case in cases:
        out = root / "preparation" / case["id"]
        out.mkdir(parents=True, exist_ok=False)
        private = json.loads((repo / case["reference_private"]).read_text())
        # Preserve full provenance and evaluator controls, but never expose gold to prompts.
        validate(case, private["source"])
        ex.write(out / "reference-private.json", private)
        ex.write(out / "qa/qa.json", json.loads((repo / case["qa_path"]).read_text()))
        ex.write(out / "accepted.json", case)
    ex.write(root / "preparation.json", {"ready": True, "accepted": len(cases), "pool_exhausted": True,
                                       "model_calls": 0, "required": plan["cases"]})
    ex.write(root / "selection.json", {"cases": cases, "indexing_allowed": False,
             "dataset_sha256": ex.file_sha256(repo / plan["dataset"]), "tool": manifest["tool"],
             "cohort_sha256": ex.file_sha256(repo / plan["cohort_manifest"])}, exclusive=True)
    return {"ready": True, "accepted": len(cases), "model_calls": 0}
