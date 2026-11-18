"""Prepare frozen SWE cases using original projects and four evaluator controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from llm_ontology.benchmarks import refactoring_execution as ex
from llm_ontology.benchmarks.matrix_support import durable_json as write
from llm_ontology.benchmarks.refactoring_pool import behavior_mutants, pool

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "configs/benchmarks/refactoring_matrix_v1.json"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def tool_identity(plan):
    classes = (REPO / plan["tool_classes"]).resolve()
    jars = sorted((REPO / plan["tool_libs"]).glob("*.jar"))
    files = [classes / "RefactoringProbe.class", classes / "RefactoringProbe$1.class", *jars]
    if not jars or any(not p.is_file() for p in files):
        raise ValueError("Build tools/refactoring-miner/pom.xml first; local detector is absent")
    java = Path(plan["tool_java_home"]) / "bin/java"
    return {"java_home": plan["tool_java_home"], "classpath": ":".join(map(str, [classes, *jars])),
            "files": {str(p): ex.file_sha256(p) for p in [java.resolve(), *files]}}


def make_case(record, spec, plan):
    if record["projectName"].lower() in plan["excluded_projects"]:
        raise ValueError("Excluded repository")
    if record["type"] not in {"Extract Method", "Inline Method"}:
        raise ValueError("Unsupported operation")
    if record["filePathBefore"] != record["filePathAfter"] or "/test/" in record["filePathBefore"]:
        raise ValueError("Single production file required")
    version = float(record["compileJDK"])
    version = "8" if version == 1.8 else str(int(version))
    java = plan["jdk_homes"].get(version)
    if not java or not all((Path(java) / "bin" / name).is_file() for name in ["java", "javac"]):
        raise ValueError("Required JDK " + version + " is not configured/installed")
    mirror, parent = ex.acquire(spec["repo"], record["commitId"], Path(plan["cache"]))
    paths = ex.checked(["git", "--git-dir", str(mirror), "ls-tree", "-r", "--name-only", parent]).splitlines()
    if "pom.xml" not in paths:
        raise ValueError("No root Maven pom.xml; Gradle/Ant project needs an explicit build profile")
    before = subprocess_source(mirror, parent, record["filePathBefore"])
    # Newlines normalized only at the dataset/checkout comparison, never code repaired.
    if before.replace("\r\n", "\n") != record["sourceCodeBeforeForWhole"].replace("\r\n", "\n"):
        raise ValueError("Dataset before file differs from actual parent checkout")
    method = record["methodNameBefore"].split("#")[-1]
    flags = ["mvn", "-B", "-q", "-Dcheckstyle.skip", "-Drat.skip=true", "-Djacoco.skip=true",
             "-Dmaven.javadoc.skip=true"]
    return {"id": record["uniqueId"], "repo": spec["repo"], "mirror": str(mirror),
            "commit": record["commitId"], "parent": parent, "file_path": record["filePathBefore"],
            "before": before, "before_sha256": sha(before), "operation": record["type"],
            "class_name": record["classNameBefore"], "target": ex.target_location(before, method),
            "java_home": java, "build": [*flags, "-DskipTests", "test-compile"],
            "test": [*flags, *(["-Dtest=" + spec["test_selector"]] if spec.get("test_selector") else []), "test"],
            "test_scope": spec.get("test_selector", "full Maven reactor unit tests"),
            "timeout": plan["project_timeout_seconds"],
            "reports": ["**/target/surefire-reports/TEST-*.xml"], "module": ".",
            "overlap": "basic lexical/commit screen; PMD excluded; not certified unseen"}


def subprocess_source(mirror, parent, file):
    ex.safe_path(file)
    return ex.checked(["git", "--git-dir", str(mirror), "show", parent + ":" + file])


def qa(case, gold, mutation, root, tool, mutation_limit=8, focus=None):
    root.mkdir(parents=True, exist_ok=False)
    baseline = [ex.execute(case, case["before"], root / f"baseline-{n}") for n in range(2)]
    if (any(r["status"] != "passed" for r in baseline)
            or baseline[0]["test_reports"]["signature"] != baseline[1]["test_reports"]["signature"]):
        raise ValueError("Original project tests/build not stable; inspect " + str(root))
    expected = baseline[0]["test_reports"]["signature"]
    reference = ex.evaluate(case, gold, root / "reference", tool, expected)
    noop = ex.evaluate(case, case["before"], root / "noop", tool, expected)
    syntax = ex.evaluate(case, "this is deliberately not Java", root / "syntax", tool, expected)
    if mutation is not None:
        old, new = mutation
        if gold.count(old) != 1:
            raise ValueError("Behavior mutation must match exactly once")
        mutants = [{"method": ["predeclared"], "source": gold.replace(old, new)}]
    else:
        mutants = behavior_mutants(case["before"], gold, mutation_limit, focus)
    controls = []
    for index, mutant in enumerate(mutants):
        if not reference["verified_success"]:
            break
        out = root / f"behavior-{index}"
        out.mkdir()
        (out / "mutant.java").write_bytes(mutant["source"].encode())
        outcomes = [ex.execute(case, mutant["source"], out / f"repeat-{n}", expected, offline=True)
                    for n in range(2)]
        killed = all(r["compiled"] and r["status"] == "test_failure"
                     and sorted(t[0] for t in r["test_reports"]["signature"]) == sorted(t[0] for t in expected)
                     and sorted(t[0] for t in r["test_reports"]["signature"] if t[1] == "skipped")
                     == sorted(t[0] for t in expected if t[1] == "skipped") for r in outcomes)
        killed = killed and outcomes[0]["test_reports"]["signature"] == outcomes[1]["test_reports"]["signature"]
        evidence = {"method": mutant["method"], "source_sha256": sha(mutant["source"]),
                    "killed": killed, "outcomes": outcomes}
        write(out / "control.json", evidence)
        controls.append(evidence)
        if killed:
            break
    checks = {"original_stable": True, "reference_accepted": reference["verified_success"],
              "noop_rejected": noop["status"] == "no_op",
              "syntax_compile_rejected": all(r["status"] == "compile_failure" for r in syntax["outcomes"]),
              "behavior_test_rejected": any(c["killed"] for c in controls)}
    result = {"checks": checks, "passed": all(checks.values()), "model_calls": 0,
              "expected_tests": expected, "baseline": baseline, "behavior_controls": controls}
    write(root / "qa.json", result)
    return result


def prepare(root, plan, validate_case):
    """Resume complete candidate controls; never silently overwrite a partial attempt."""
    records, overrides, identity = pool(REPO, plan)
    if identity != plan["pool_identity"]:
        raise ValueError("Audited candidate pool changed; use a new run-id")
    tool = tool_identity(plan)
    dataset = REPO / plan["dataset"]
    accepted, rejected = [], []
    for record in records:
        spec = overrides.get(record["uniqueId"], {"repo": plan["repositories"][record["projectName"]]})
        out = root / "preparation" / record["uniqueId"]
        if (out / "accepted.json").exists():
            accepted.append(json.loads((out / "accepted.json").read_text()))
        elif (out / "rejected.json").exists():
            rejected.append(json.loads((out / "rejected.json").read_text()))
        else:
            if out.exists():
                raise ValueError("Interrupted partial preparation; preserve evidence and use a new run-id: " + str(out))
            print("PREPARE", record["uniqueId"], flush=True)
            try:
                case = make_case(record, spec, plan)
                sizes = validate_case(case, record["sourceCodeAfterForWhole"])
                write(out / "prompt_size.json", sizes)
                control = qa(case, record["sourceCodeAfterForWhole"], spec.get("mutation"), out / "qa", tool,
                             plan["mutation_limit"], record["sourceCodeAfterRefactoring"])
                if not control["passed"]:
                    raise ValueError("Evaluator controls failed: " + str(control["checks"]))
                case["expected_tests"] = control["expected_tests"]
                write(out / "reference-private.json", {"source": record["sourceCodeAfterForWhole"]})
                write(out / "accepted.json", case)
                accepted.append(case)
            except Exception as exc:
                failure = {"id": record["uniqueId"], "reason": str(exc)}
                write(out / "rejected.json", failure)
                rejected.append(failure)
                print("REJECTED", failure, flush=True)
        progress = {"accepted": len(accepted), "rejected": len(rejected), "pool_size": len(records),
                    "required": plan["cases"], "last_id": record["uniqueId"], "model_calls": 0}
        write(root / "preparation_progress.json", progress)
        if plan["cases"] != "all" and len(accepted) >= plan["cases"]:
            break
    result = {"protocol": plan["protocol"], "accepted": len(accepted), "required": plan["cases"],
              "pool_size": len(records), "pool_exhausted": len(accepted) + len(rejected) == len(records),
              "rejected": rejected, "model_calls": 0,
              "ready": bool(accepted) if plan["cases"] == "all" else len(accepted) == plan["cases"]}
    write(root / "preparation.json", result)
    if result["ready"] and not (root / "selection.json").exists():
        # Gold never enters the public case/manifest or retrieval query.
        write(root / "selection.json", {"cases": accepted, "indexing_allowed": False,
            "dataset_sha256": ex.file_sha256(dataset), "tool": tool}, exclusive=True)
    return result
