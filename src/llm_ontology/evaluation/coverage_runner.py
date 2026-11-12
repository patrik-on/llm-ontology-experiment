"""Pinned, opt-in JaCoCo measurements over reviewed local Java code (not a sandbox).

Reuses the shared Jupiter execution gate. Only the focal production .class is
reported, never generated tests/dependencies. Production must be compiled with -g.
Missing evidence is null with a reason, never an invented zero. No model calls,
source rewriting, production rebuilding, downloads or repeated execution occur here.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET

from llm_ontology.benchmarks.defects4j_execution import (
    clean_env, evaluate_revision, file_sha256, java_identity, run_process, write_json,
)

JACOCO_VERSION = "0.8.13"
AGENT_SHA256 = "47e700ccb0fdb9e27c5241353f8161938f4e53c3561dd35e063c5fe88dc3349b"
CLI_SHA256 = "8f748683833d4dc4d72cea5d6b43f49344687b831e0582c97bcb9b984e3de0a3"


def _counter(node: ET.Element, kind: str) -> dict[str, Any]:
    matches = [c for c in node.findall("counter") if c.get("type") == kind]
    unavailable = {"missed": None, "covered": None, "total": None, "ratio": None}
    if len(matches) != 1:
        return {**unavailable, "reason": "missing_counter" if not matches else "duplicate_counter"}
    try:
        missed, covered = (int(matches[0].attrib[k]) for k in ("missed", "covered"))
        if missed < 0 or covered < 0:
            raise ValueError("Negative counter")
    except (ValueError, KeyError):
        return {**unavailable, "reason": "invalid_counter"}
    total = missed + covered
    return {"missed": missed, "covered": covered, "total": total,
            "ratio": covered / total if total else None,
            "reason": None if total else "zero_total"}


def _metrics(node: ET.Element) -> dict[str, Any]:
    return {kind.lower(): _counter(node, kind) for kind in ("LINE", "BRANCH", "METHOD")}


def read_jacoco_xml(xml: Path, focal_class: str, focal_method: str) -> dict[str, Any]:
    """Name must be unique, or use name + JVM descriptor, e.g. classify(I)I.

    JaCoCo omits BRANCH counters when no branches exist. Omission stays null,
    with missing_counter (not a claimed zero or a 100% score). LINE and METHOD
    must be present and positive-total at both scopes for a valid measurement.
    """
    result: dict[str, Any] = {"status": "unavailable", "reason": None,
                              "class": None, "method": None, "focal_invoked": None}
    try:
        root = ET.parse(xml).getroot()
    except (OSError, ET.ParseError) as exc:
        return {**result, "reason": "invalid_or_missing_xml", "error": str(exc)}
    classes = [c for c in root.findall("./package/class")
               if c.get("name") == focal_class.replace(".", "/")]
    if len(classes) != 1:
        return {**result, "reason": "missing_class" if not classes else "ambiguous_class"}
    cls = classes[0]
    result["class"] = {"name": focal_class, "counters": _metrics(cls)}
    methods = [m for m in cls.findall("method")
               if m.get("name") == focal_method or
               (m.get("name", "") + m.get("desc", "")) == focal_method]
    if len(methods) != 1:
        return {**result, "reason": "missing_method" if not methods else "ambiguous_method"}
    method = methods[0]
    result["method"] = {"name": method.get("name"), "descriptor": method.get("desc"),
                        "counters": _metrics(method)}
    method_count = result["method"]["counters"]["method"]
    if method_count["total"] != 1:
        return {**result, "reason": "invalid_or_missing_method_counter"}
    # This is instrumentation evidence, not a source-text invocation heuristic.
    result["focal_invoked"] = method_count["covered"] == 1
    for scope in ("class", "method"):
        for kind in ("line", "method"):
            count = result[scope]["counters"][kind]
            if count["ratio"] is None:
                return {**result, "status": "incomplete", "reason": f"{scope}_{kind}_unavailable"}
        branch = result[scope]["counters"]["branch"]
        if branch["reason"] not in (None, "missing_counter", "zero_total"):
            return {**result, "status": "incomplete", "reason": f"{scope}_branch_invalid"}
    return {**result, "status": "measured"}


def run_jacoco_coverage(source: str, revision: dict[str, Any], *, output: Path | str,
                        java_home: Path | str, junit_jar: Path | str, junit_sha256: str,
                        agent_jar: Path | str, cli_jar: Path | str,
                        focal_class: str, focal_method: str, timeout: int = 30) -> dict[str, Any]:
    """Execute once, returning success-only coverage and separate failed-run diagnostics.

    revision has the same bin_classes/dependencies contract as evaluate_revision.
    output must not exist. Returned status is the shared execution status;
    coverage_status is independent. coverage is non-null ONLY for a passed class
    with valid metrics. diagnostic_coverage may expose failed-run instrumentation,
    explicitly excluded from success metrics. See coverage.json for persisted data.
    """
    output, java_home, junit_jar, agent_jar, cli_jar = (
        Path(p).resolve() for p in (output, java_home, junit_jar, agent_jar, cli_jar))
    if timeout <= 0:
        raise ValueError("Positive timeout required.")
    if not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", focal_class):
        raise ValueError("Invalid focal class FQN.")
    if not focal_method:
        raise ValueError("Focal method required.")
    for jar, expected in ((agent_jar, AGENT_SHA256), (cli_jar, CLI_SHA256)):
        if file_sha256(jar) != expected:
            raise ValueError(f"Pinned JaCoCo checksum mismatch: {jar.name}")
    if any(c in str(output) or c in str(agent_jar) for c in (",", "=", "\n", "\r")):
        raise ValueError("Unsupported JaCoCo option delimiter in path.")
    production = Path(revision["bin_classes"]).resolve()
    class_file = production / (focal_class.replace(".", "/") + ".class")
    if not class_file.is_file() or not class_file.resolve().is_relative_to(production):
        raise ValueError("Focal compiled production class is unavailable.")
    try:
        _, test_class = java_identity(source)
    except ValueError:
        test_class = None  # Let the shared evaluator classify invalid generated source.
    if test_class == focal_class:
        raise ValueError("Generated test cannot shadow the focal production class.")
    production_sha256 = file_sha256(class_file)
    output.mkdir(parents=True, exist_ok=False)
    exec_file, xml = output / "jacoco.exec", output / "jacoco.xml"
    agent = (f"-javaagent:{agent_jar}=destfile={exec_file},append=false,"
             f"includes={focal_class},dumponexit=true,output=file")
    execution = evaluate_revision(
        source, revision, output=output / "evaluation", java_home=java_home,
        junit_jar=junit_jar, junit_sha256=junit_sha256, timeout=timeout, java_options=[agent])
    result: dict[str, Any] = {
        "status": execution["status"], "execution": execution,
        "coverage_status": "unavailable", "coverage_reason": None,
        "coverage": None, "diagnostic_coverage": None,
        "focal_invoked": None, "focal_class": focal_class, "focal_method": focal_method,
        "jacoco_version": JACOCO_VERSION, "agent_sha256": AGENT_SHA256,
        "cli_sha256": CLI_SHA256, "production_class": str(class_file),
        "production_class_sha256": production_sha256,
        "sandbox": "none-local-reviewed-diagnostic-only",
    }
    if not exec_file.is_file() or exec_file.stat().st_size == 0:
        result["coverage_reason"] = "missing_execution_data"
    else:
        result["exec"] = {"path": str(exec_file), "sha256": file_sha256(exec_file)}
        report = run_process(
            [str(java_home / "bin/java"), "-Xmx256m", "-jar", str(cli_jar), "report",
             str(exec_file), "--classfiles", str(class_file), "--xml", str(xml)],
            output, clean_env(output / "report-home", java_home), timeout, output / "jacoco-report.log")
        result["report"] = report
        log = (output / "jacoco-report.log").read_text(encoding="utf-8", errors="replace")
        if report["status"] != "completed" or report.get("returncode") != 0:
            result["coverage_reason"] = "report_failed"
        elif "does not match" in log or "do not match" in log:
            result["coverage_reason"] = "execution_class_mismatch"
        elif file_sha256(class_file) != result["production_class_sha256"]:
            result["coverage_reason"] = "production_class_changed"
        else:
            metrics = read_jacoco_xml(xml, focal_class, focal_method)
            result["coverage_status"] = metrics["status"]
            result["coverage_reason"] = metrics["reason"]
            if xml.is_file():
                result["xml"] = {"path": str(xml), "sha256": file_sha256(xml)}
            if execution["status"] == "passed" and metrics["status"] == "measured":
                result["coverage"] = metrics
                result["focal_invoked"] = metrics["focal_invoked"]
            else:
                result["diagnostic_coverage"] = metrics
                if execution["status"] != "passed":
                    result["coverage_status"] = "diagnostic_only"
                    result["coverage_reason"] = "test_class_not_passed"
    write_json(output / "coverage.json", result)
    return result
