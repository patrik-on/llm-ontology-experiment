"""Offline evaluation of immutable model bodies, no new generation or repair."""

from __future__ import annotations
import argparse
from pathlib import Path
import re
from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test_pilot import ARMS, read
from llm_ontology.benchmarks.methods2test_metrics import evaluate
from llm_ontology.benchmarks.methods2test_report import test_outcomes
from llm_ontology.benchmarks.methods2test_selection import words

# Conservative local execution review, NOT sandboxing/security proof. Rejected
# candidates stay in denominators and their original bytes remain untouched.
UNSAFE = {
    "System",
    "Runtime",
    "ProcessBuilder",
    "Thread",
    "ThreadGroup",
    "ClassLoader",
    "URLClassLoader",
    "File",
    "Files",
    "Paths",
    "Path",
    "Socket",
    "ServerSocket",
    "DatagramSocket",
    "Unsafe",
    "MethodHandles",
    "ManagementFactory",
    "Desktop",
    "Robot",
    "RandomAccessFile",
    "FileInputStream",
    "FileOutputStream",
    "URL",
    "URLConnection",
    "HttpURLConnection",
    "HttpClient",
    "PrintWriter",
    "PrintStream",
    "FileReader",
    "FileWriter",
    "Scanner",
    "FileChannel",
    "AsynchronousFileChannel",
    "SocketChannel",
    "DatagramChannel",
    "InitialContext",
    "ScriptEngine",
    "ScriptEngineManager",
    "Timer",
    "Executors",
    "Class",
    "Method",
    "Field",
    "Constructor",
    "AccessibleObject",
    "ObjectInputStream",
    "ObjectOutputStream",
}


def review(root):
    reviews = {}
    rejected = {}
    for ident in read(root / "selection.json")["ids"]:
        for arm in ARMS:
            out = root / "cases" / ident / "predictions" / arm
            source = out / "generated.java"
            if not source.exists():
                continue
            text = source.read_text()
            digest = file_sha256(source)
            if digest != read(out / "generation.json")["source_sha256"]:
                raise ValueError("candidate_bytes_changed")
            lexical = words(text)
            bad = sorted(lexical & UNSAFE)
            # No reflection, dynamic execution, environment/network/filesystem
            # access. Loops are allowed only under existing bounded process guard.
            if bad or re.search(
                r"java\.lang\.reflect|\bgetClass\s*\(|\bClass\s*\.\s*forName|\b(?:exec|exit|halt|loadLibrary|setSecurityManager)\s*\(",
                text,
            ):
                reason = "local_source_review_rejected:" + ",".join(bad)
                rejected[ident + "/" + arm] = {"sha256": digest, "reason": reason}
                if not (out / "metrics.json").exists():
                    write_json(
                        out / "metrics.json",
                        {
                            "id": ident,
                            "arm": arm,
                            "source_sha256": digest,
                            "syntax_parse": True,
                            "compiled": False,
                            "positive_nonaborted_execution": False,
                            "class_pass": False,
                            "statuses": ["source_review_rejected"],
                            "repeat_stable": None,
                            "tests_first_run": {},
                            "focal_invoked_accepted": False,
                            "coverage": None,
                            "coverage_reason": reason,
                            "diagnostic_coverage": None,
                            "repeat_coverage_equal": None,
                            "outcomes": [],
                        },
                    )
                continue
            reviews[ident + "/" + arm] = digest
    write_json(root / "reviewed_sources.json", reviews)
    write_json(root / "source_review_rejections.json", rejected)
    return reviews


def run(root):
    reviews = review(root)
    evaluate(root, reviews)
    for ident in read(root / "selection.json")["ids"]:
        for arm in ARMS:
            out = root / "cases" / ident / "predictions" / arm
            p = out / "metrics.json"
            if not p.exists():
                continue
            m = read(p)
            if len(m.get("outcomes", [])) != 2:
                continue
            signatures = [test_outcomes(out / f"coverage-{i}/evaluation/reports") for i in range(2)]
            m["per_test_outcomes_first_run"] = signatures[0]
            m["per_test_outcomes_repeat_equal"] = (
                signatures[0] == signatures[1] if signatures[0] else None
            )
            m["repeat_stable"] = m["repeat_stable"] and (
                m["per_test_outcomes_repeat_equal"] is not False
            )
            if m["class_pass"] and m["coverage"] is None:
                m["coverage_reason"] = (
                    m.get("coverage_reason") or "passing_suite_coverage_infrastructure_unavailable"
                )
            write_json(p, m)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id

    validate_evaluation_run_id(a.run_id)
    run((Path("artifacts/evaluation/runs") / a.run_id).resolve())


if __name__ == "__main__":
    main()
