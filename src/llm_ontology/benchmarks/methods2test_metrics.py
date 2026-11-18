'Internal JaCoCo and execution metrics for the current Methods2Test matrix.'

from __future__ import annotations

from pathlib import Path

import re

from llm_ontology.benchmarks.java_execution import file_sha256, write_json

from llm_ontology.benchmarks.matrix_support import ARMS, read, runtime

from llm_ontology.evaluation.coverage_runner import run_jacoco_coverage

from llm_ontology.ingestion.java import JavaParser

def measure(source, prepared, output):
    c = runtime()
    pins = read(Path("configs/evaluation/jacoco_v1.json"))
    # Tool paths are separately pinned by the coverage runner's embedded SHA-256.
    agent = Path("/home/patrik/benchmark-work/downloads/org.jacoco.agent-0.8.13-runtime.jar")
    cli = Path("/home/patrik/benchmark-work/downloads/org.jacoco.cli-0.8.13-nodeps.jar")
    if not pins:
        raise ValueError("Missing coverage manifest")
    return run_jacoco_coverage(source, prepared["revision"], output=output,
        java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256,
        agent_jar=agent, cli_jar=cli, focal_class=prepared["focal_class"], focal_method=prepared["focal_method"])

def evaluate(root, reviews, *, arms=ARMS):
    parser = JavaParser()
    for ident in read(root / "selection.json")["ids"]:
        cr = root / "cases" / ident
        prepared = read(cr / "prepared.json")
        for arm in arms:
            out = cr / "predictions" / arm
            if not (out / "generated.java").exists():
                continue
            if (out / "metrics.json").exists():
                continue
            key = ident + "/" + arm
            digest = file_sha256(out / "generated.java")
            if digest != reviews.get(key) or digest != read(out / "generation.json")["source_sha256"]:
                raise ValueError("Missing matching reviewed-source hash: " + key)
            source = (out / "generated.java").read_text()
            write_json(out / "review.json", {"source_sha256": digest, "reviewed_local_execution": True, "security_sandbox": False})
            results = []
            for i in range(2):
                path = out / ("coverage-" + str(i))
                results.append(read(path / "coverage.json") if (path / "coverage.json").exists() else measure(source, prepared, path))
            summaries = [r["execution"].get("console_summary", {}) for r in results]
            outcomes = [r["status"] for r in results]
            # Presence only, NOT semantic assertion quality or proof against vacuity.
            lexical_assertions = len(re.findall(r"\b(?:assert[A-Z]\w*|fail)\s*\(",
                "\n".join(read(out / "bodies.json").values())))
            result = {"id": ident, "arm": arm, "source_sha256": digest,
                "syntax_parse": parser.parse(source).parse_success, "assertion_calls_lexical_diagnostic": lexical_assertions,
                "compiled": all(r["execution"].get("compile", {}).get("returncode") == 0 for r in results),
                "positive_nonaborted_execution": all(s.get("tests_started", 0) > 0 and s.get("tests_aborted", 0) == 0 and s.get("containers_failed", 0) == 0 for s in summaries),
                "class_pass": all(o == "passed" for o in outcomes), "statuses": outcomes,
                "repeat_stable": outcomes[0] == outcomes[1] and summaries[0] == summaries[1],
                "tests_first_run": summaries[0], "focal_invoked_accepted": all(r["focal_invoked"] is True for r in results),
                "coverage": results[0]["coverage"] if all(o == "passed" for o in outcomes) else None,
                "coverage_reason": results[0]["coverage_reason"],
                "diagnostic_coverage": results[0]["diagnostic_coverage"],
                "repeat_coverage_equal": results[0]["coverage"] == results[1]["coverage"],
                "outcomes": results}
            write_json(out / "metrics.json", result)
            print("EVALUATED", ident, arm, outcomes, flush=True)
