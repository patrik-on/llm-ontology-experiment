"""Fail-closed, model-free single-file SWE refactoring evaluation (WSL).

Trusted build commands run in disposable project copies. This is isolation from
other attempts, NOT an OS security sandbox or a proof of semantic equivalence.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from time import perf_counter
import xml.etree.ElementTree as ET
from uuid import uuid4

from pydantic import BaseModel, Field

from llm_ontology.core.paths import work_root_path

from llm_ontology.benchmarks.java_execution import file_sha256, run_process
from llm_ontology.benchmarks.matrix_support import durable_json as write
from llm_ontology.ingestion.identity import normalize_java_for_hash
from llm_ontology.ingestion.java import JavaParser


class FileAnswer(BaseModel):
    model_config = {"extra": "forbid", "strict": True}
    file_path: str = Field(min_length=1)
    refactored_code: str = Field(min_length=1)


def read_utf8(path: Path) -> str:
    """Do not silently rewrite CRLF in frozen prompts or candidate code."""
    return path.read_bytes().decode("utf-8")


def parse_answer(raw: str, allowed: str) -> str:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key: " + key)
            value[key] = item
        return value
    answer = FileAnswer.model_validate(json.loads(raw, object_pairs_hook=unique))
    safe_path(answer.file_path)
    if answer.file_path != allowed or chr(0) in answer.refactored_code:
        raise ValueError("Wrong allowed path or NUL source")
    return answer.refactored_code


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or "\\" in value or ":" in value
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("Unsafe repository-relative path: " + value)
    return path


def target_location(source: str, method: str) -> dict:
    raw = source.encode()
    root = JavaParser().parser.parse(raw).root_node
    matches = []
    def visit(node):
        if node.type == "method_declaration":
            name = node.child_by_field_name("name")
            if raw[name.start_byte:name.end_byte].decode() == method:
                matches.append(node)
        for child in node.named_children:
            visit(child)
    visit(root)
    if root.has_error or len(matches) != 1:
        raise ValueError("Invalid Java or ambiguous target overload; explicit disambiguation needed")
    node = matches[0]
    # RM includes attached Javadoc in declaration locations; Tree-sitter doesn't.
    previous = node.prev_named_sibling
    start = node.start_point.row + 1
    if (previous is not None and previous.type == "block_comment"
            and raw[previous.start_byte:previous.end_byte].startswith(b"/**")
            and not raw[previous.end_byte:node.start_byte].strip()):
        start = previous.start_point.row + 1
    return {"start": start, "end": node.end_point.row + 1,
            "method": method}


def checked(command, cwd=None, timeout=180):
    return subprocess.check_output(command, cwd=cwd, timeout=timeout, stderr=subprocess.STDOUT).decode()


def acquire(repo: str, commit: str, cache: Path) -> tuple[Path, str]:
    """Fetch only the named commit and its parent; never alter a user checkout."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("Expected pinned GitHub repository and full SHA")
    mirror = cache / (repo.replace("/", "--") + ".git")
    if not mirror.exists():
        mirror.parent.mkdir(parents=True, exist_ok=True)
        checked(["git", "init", "--bare", str(mirror)])
    try:
        parent = checked(["git", "--git-dir", str(mirror), "rev-parse", commit + "^1"]).strip()
    except subprocess.CalledProcessError:
        checked(["git", "--git-dir", str(mirror), "fetch", "--depth=2", "--no-tags",
                 "https://github.com/" + repo + ".git", commit], timeout=300)
        parent = checked(["git", "--git-dir", str(mirror), "rev-parse", commit + "^1"]).strip()
    return mirror, parent


def checkout(mirror: Path, parent: str, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(["git", "--git-dir", str(mirror), "archive", parent])
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(output, filter="data")


def reports(project: Path, patterns: list[str]) -> dict:
    paths = sorted({p for pattern in patterns for p in project.glob(pattern)})
    cases, failed, skipped = [], [], []
    try:
        for path in paths:
            root = ET.parse(path).getroot()
            for suite in ([root] if root.tag == "testsuite" else root.findall("testsuite")):
                nodes = suite.findall("testcase")
                if int(suite.get("tests", "-1")) != len(nodes):
                    raise ValueError("Suite count differs from testcase elements")
                for node in nodes:
                    ident = node.get("classname", "") + "#" + node.get("name", "")
                    if not node.get("classname") or not node.get("name"):
                        raise ValueError("Missing test identity")
                    status = ("skipped" if node.find("skipped") is not None else "failed"
                              if node.find("failure") is not None or node.find("error") is not None
                              else "passed")
                    cases.append((ident, status))
                    if status == "failed":
                        failed.append(ident)
                    if status == "skipped":
                        skipped.append(ident)
                for tag in ["failures", "errors", "skipped"]:
                    observed = sum(n.find({"failures": "failure", "errors": "error",
                                          "skipped": "skipped"}[tag]) is not None for n in nodes)
                    if int(suite.get(tag, "0")) != observed:
                        raise ValueError("Suite status count mismatch")
    except (ET.ParseError, ValueError) as exc:
        return {"status": "report_error", "error": str(exc)}
    executed = len(cases) - len(skipped)
    return {"status": "no_tests" if not executed else "test_failure" if failed else "passed",
            "executed": executed, "skipped": len(skipped), "failed": failed,
            "signature": sorted([list(c) for c in cases]),
            "reports": {str(p.relative_to(project)): file_sha256(p) for p in paths}}


def operation_matches(event: dict, case: dict) -> bool:
    target = case["target"]
    return (event.get("type") == case["operation"] and event.get("path") == case["file_path"]
            and event.get("target_class") == case["class_name"]
            and event.get("target_method") == target["method"]
            and target["start"] <= event.get("target_start", -1) <= target["end"]
            and event.get("target_end") == target["end"])


def detect(case: dict, source: str, output: Path, tool: dict) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    before, after, events = output / "before.java", output / "after.java", output / "events.json"
    before.write_text(case["before"], encoding="utf-8")
    after.write_text(source, encoding="utf-8")
    result = run_process([str(Path(tool["java_home"]) / "bin/java"), "-cp", tool["classpath"],
                          "RefactoringProbe", case["file_path"], str(before), str(after), str(events)],
                         output, os.environ.copy(), 90, output / "detector.log")
    if result.get("returncode") != 0 or not events.exists():
        return {"status": "detector_error", "process": result}
    try:
        payload = json.loads(events.read_text())
        if payload["version"] != "3.0.10" or not isinstance(payload["events"], list):
            raise ValueError("Unexpected detector output")
        matching = [e for e in payload["events"] if operation_matches(e, case)]
        return {"status": "matched" if matching else "operation_missing", "matching": matching,
                "events": payload["events"], "process": result}
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "detector_error", "error": str(exc), "process": result}


def execute(case: dict, source: str, output: Path, expected=None, *, offline=False) -> dict:
    """One fresh archive for compilation and tests; no stale build/test artifacts."""
    output.mkdir(parents=True, exist_ok=False)
    # NTFS/OneDrive is very slow for historical Java source/build trees under WSL.
    # Keep evidence in the run directory, but isolated working copies on Linux FS.
    project = Path(case.get("work_root") or work_root_path("refactoring-matrix", "executions")) / uuid4().hex
    write(output / "workspace.json", {"path": str(project)})
    checkout(Path(case["mirror"]), case["parent"], project)
    target = project / safe_path(case["file_path"])
    if target.is_symlink() or file_sha256(target) != case["before_sha256"]:
        raise ValueError("Original checkout does not match frozen source")
    # Assert the resolved target stays inside this attempt even with repository symlinks.
    target.resolve().relative_to(project.resolve())
    target.write_text(source, encoding="utf-8")
    env = {**os.environ, "JAVA_HOME": case["java_home"],
           "PATH": case["java_home"] + "/bin:" + os.environ["PATH"]}
    env.pop("JAVA_TOOL_OPTIONS", None)
    env.pop("_JAVA_OPTIONS", None)
    cwd = project / safe_path(case.get("module", ".")) if case.get("module", ".") != "." else project
    build = [case["build"][0], "-o", *case["build"][1:]] if offline else case["build"]
    test = [case["test"][0], "-o", *case["test"][1:]] if offline else case["test"]
    compiled = run_process(build, cwd, env, case["timeout"], output / "build.log", open_files=8192)
    if compiled["status"] != "completed" or compiled.get("returncode") != 0:
        return {"status": "build_timeout" if compiled["status"] == "timeout" else
                "infrastructure_error" if compiled["status"] == "infrastructure_error" else "compile_failure",
                "build": compiled, "compiled": False}
    # Build can execute tests unexpectedly. Remove only report XML created in our new copy.
    for pattern in case["reports"]:
        for path in project.glob(pattern):
            path.resolve().relative_to(project.resolve())
            path.unlink()
    tested = run_process(test, cwd, env, case["timeout"], output / "test.log", open_files=8192)
    parsed = reports(project, case["reports"])
    status = ("test_timeout" if tested["status"] == "timeout" else parsed["status"])
    if tested["status"] == "infrastructure_error":
        status = "infrastructure_error"
    if tested.get("returncode") != 0 and status == "passed":
        status = "test_process_error"
    if status == "passed" and expected is not None and parsed["signature"] != expected:
        status = "test_set_changed"
    return {"status": status, "compiled": True, "build": compiled, "test": tested,
            "test_reports": parsed}


def evaluate(case: dict, source: str, output: Path, tool: dict, expected=None) -> dict:
    from llm_ontology.benchmarks.refactoring_structural import valid_java
    output.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    result = {"verified_success": False, "structural_success": False,
              "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
    if normalize_java_for_hash(source) == normalize_java_for_hash(case["before"]):
        result["status"] = "no_op"
    else:
        result["operation"] = detect(case, source, output / "operation", tool)
        # SWE scope remains the one frozen production file plus exact original
        # class/method/location binding. RM omits some legitimate call sites
        # (e.g. a field initializer calling the extracted helper); do not mistake
        # its locations for a complete edit set. Existing builds/tests stay strict.
        result["structural_success"] = valid_java(source) and result["operation"]["status"] == "matched"
        result["outcomes"] = [execute(case, source, output / f"repeat-{n}", expected, offline=True)
                              for n in range(2)]
        stable = (all(r["status"] == "passed" for r in result["outcomes"])
                  and result["outcomes"][0]["test_reports"]["signature"]
                  == result["outcomes"][1]["test_reports"]["signature"])
        result["verified_success"] = stable and result["structural_success"]
        result["status"] = ("passed" if result["verified_success"] else
                            "detector_error" if result["operation"]["status"] == "detector_error" else
                            "checks_failed")
    result["seconds"] = perf_counter() - start
    write(output / "evaluation.json", result)
    return result
