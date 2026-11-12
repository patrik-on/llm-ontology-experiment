"""Bounded Jupiter adapter over Defects4J exports (not the native JUnit4 runner).

Process groups, resource limits and a scrubbed environment are defense in depth,
NOT a security sandbox. Only reviewed code may execute on this local host.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import xml.etree.ElementTree as ET
from typing import Any

from llm_ontology.ingestion.identity import normalize_java_for_hash

D4J_COMMIT = "6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09"
JUNIT_VERSION = "1.11.4"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_env(home: Path, java_home: Path, *, tool_paths: tuple[Path, ...] = ()) -> dict[str, str]:
    """Allowlist rather than blacklist: no inherited tokens, agent sockets or rc hooks."""
    home.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home), "JAVA_HOME": str(java_home),
        "PATH": ":".join(str(p) for p in (java_home / "bin", *tool_paths)) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "America/Los_Angeles",
        "TMPDIR": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    }


def _limits() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))


def run_process(command: list[str], cwd: Path, env: dict[str, str], timeout: int,
                log: Path) -> dict[str, Any]:
    if os.name != "posix":
        raise RuntimeError("Defects4J execution requires WSL/Linux.")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=_limits)
        except OSError as exc:
            return {"status": "infrastructure_error", "error": str(exc), "command": command}
        try:
            code = process.wait(timeout=timeout)
            status = "completed"
        except subprocess.TimeoutExpired:
            status = "timeout"
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
        finally:
            # Also terminate descendants if the parent exited without waiting for them.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return {"status": status, "returncode": code, "command": command,
            "log": str(log), "log_sha256": file_sha256(log)}


def java_identity(source: str) -> tuple[str, str]:
    lexical = normalize_java_for_hash(source)
    # Strip literals as well so source strings cannot impersonate declarations.
    lexical = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", '""', lexical)
    classes = re.findall(r"\b(?:public\s+)?(?:final\s+)?class\s+([A-Za-z_$][\w$]*)", lexical)
    if len(classes) != 1:
        raise ValueError("Exactly one generated test class is required; nested classes unsupported.")
    package = re.search(r"\bpackage\s+([\w$]+(?:\s*\.\s*[\w$]+)*)\s*;", lexical)
    namespace = re.sub(r"\s", "", package.group(1)) if package else ""
    name = classes[0]
    return name, f"{namespace}.{name}" if namespace else name


def read_jupiter_reports(reports: Path, selected_class: str) -> dict[str, Any]:
    """Read only a fresh directory supplied by evaluate_revision; never trust exit=0."""
    cases = []
    try:
        for report in sorted(reports.glob("TEST-*.xml")):
            root = ET.parse(report).getroot()
            cases.extend(case for case in root.iter("testcase")
                         if case.attrib.get("classname") == selected_class)
    except (ET.ParseError, OSError) as exc:
        return {"status": "infrastructure_error", "error": str(exc)}
    skipped = sum(case.find("skipped") is not None for case in cases)
    executed = len(cases) - skipped
    failures = [failure for case in cases for failure in case.findall("failure")]
    errors = [error for case in cases for error in case.findall("error")]
    assertion_types = {"org.opentest4j.AssertionFailedError", "java.lang.AssertionError",
                       "org.junit.ComparisonFailure", "org.opentest4j.MultipleFailuresError"}
    assertion_only = bool(failures) and all(f.attrib.get("type") in assertion_types for f in failures)
    status = ("no_tests" if executed <= 0 else "execution_error" if errors else
              "assertion_failure" if assertion_only else "execution_error" if failures else "passed")
    return {"status": status, "selected_class": selected_class, "executed": executed,
            "skipped": skipped, "failures": len(failures), "errors": len(errors),
            "reports": [{"path": str(p), "sha256": file_sha256(p)}
                        for p in sorted(reports.glob("TEST-*.xml"))]}


def read_console_summary(text: str) -> dict[str, int]:
    """Pinned Console summary distinguishes XML-synthesized setup errors from tests started."""
    fields = ("tests found", "tests skipped", "tests started", "tests aborted",
              "tests successful", "tests failed", "containers failed")
    summary = {}
    for field in fields:
        values = re.findall(r"\[\s*(\d+)\s+" + re.escape(field) + r"\s*\]", text)
        if len(values) != 1:
            raise ValueError(f"Expected one fresh JUnit summary count for {field!r}.")
        summary[field.replace(" ", "_")] = int(values[0])
    return summary


def evaluate_revision(source: str, revision: dict[str, Any], *, output: Path,
                      java_home: Path, junit_jar: Path, junit_sha256: str,
                      timeout: int = 30) -> dict[str, Any]:
    """Compile only generated source against production outputs; execute only Jupiter."""
    if file_sha256(junit_jar) != junit_sha256:
        raise ValueError("Pinned JUnit console checksum mismatch.")
    # Exclusive work directories reject stale reports and accidental resume overwrite.
    output.mkdir(parents=True, exist_ok=False)
    try:
        name, qualified = java_identity(source)
    except ValueError as exc:
        result = {"status": "invalid_source", "error": str(exc),
                  "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
        write_json(output / "result.json", result)
        return result
    java_file = output / f"{name}.java"
    java_file.write_text(source, encoding="utf-8")
    classes = output / "classes"
    classes.mkdir()
    reports = output / "reports"
    reports.mkdir()
    env = clean_env(output / "home", java_home)
    classpath = ":".join([revision["bin_classes"], *revision["dependencies"], str(junit_jar)])
    compile_result = run_process(
        [str(java_home / "bin/javac"), "-encoding", "UTF-8", "-proc:none", "-cp", classpath,
         "-d", str(classes), str(java_file)], output, env, timeout, output / "compile.log")
    result = {"source_sha256": file_sha256(java_file), "revision": revision,
              "compile": compile_result, "junit_sha256": junit_sha256}
    if compile_result["status"] != "completed":
        result["status"] = compile_result["status"]
    elif compile_result["returncode"] != 0:
        result["status"] = "compile_failure"
    else:
        execution = run_process(
            [str(java_home / "bin/java"), "-Xmx512m", "-jar", str(junit_jar), "execute",
             "--class-path", f"{classes}:{classpath}", "--select-class", qualified,
             "--include-engine", "junit-jupiter", "--fail-if-no-tests",
             "--reports-dir", str(reports), "--disable-banner", "--disable-ansi-colors", "--details=summary"],
            output, env, timeout, output / "execution.log")
        result["execution"] = execution
        report = read_jupiter_reports(reports, qualified)
        result["discovery"] = report
        if execution["status"] == "completed":
            try:
                summary = read_console_summary((output / "execution.log").read_text(encoding="utf-8"))
                result["console_summary"] = summary
                report["xml_executed"] = report.get("executed", 0)
                report["executed"] = summary["tests_started"] - summary["tests_aborted"]
                report["aborted"] = summary["tests_aborted"]
                if report["status"] == "infrastructure_error":
                    pass  # A launcher summary cannot repair malformed/missing XML evidence.
                elif summary["containers_failed"]:
                    report["status"] = "container_failure"
                elif summary["tests_aborted"]:
                    report["status"] = "test_aborted"
                elif report["executed"] <= 0:
                    report["status"] = "no_tests"
                elif report.get("xml_executed", 0) <= 0:
                    report["status"] = "infrastructure_error"
                elif summary["tests_failed"] and report["status"] == "passed":
                    report["status"] = "execution_error"
            except (ValueError, OSError) as exc:
                report["status"] = "infrastructure_error"
                report["summary_error"] = str(exc)
        result["status"] = (execution["status"] if execution["status"] != "completed"
                            else report["status"])
        if result["status"] == "passed" and execution["returncode"] != 0:
            result["status"] = "infrastructure_error"
        if result["status"] == "assertion_failure" and execution["returncode"] != 1:
            result["status"] = "infrastructure_error"
        if result["status"] == "no_tests" and execution["returncode"] not in (0, 2):
            result["status"] = "discovery_failure"
    write_json(output / "result.json", result)
    return result


def evaluate_pair(source: str, prepared: dict[str, Any], *, output: Path,
                  java_home: Path, junit_jar: Path, junit_sha256: str,
                  timeout: int = 30, repeats: int = 2) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("Stability requires at least two independent executions per revision.")
    if prepared["fixed"]["dependency_hashes"] != prepared["buggy"]["dependency_hashes"]:
        raise ValueError("Fixed/buggy dependency identities differ.")
    outcomes = {version: [evaluate_revision(
        source, prepared[version], output=output / f"{version}-{index}", java_home=java_home,
        junit_jar=junit_jar, junit_sha256=junit_sha256, timeout=timeout)
        for index in range(repeats)] for version in ("fixed", "buggy")}
    fixed_pass = all(item["status"] == "passed" for item in outcomes["fixed"])
    detected = fixed_pass and all(item["status"] == "assertion_failure"
                                  for item in outcomes["buggy"])
    statuses = {version: [item["status"] for item in items] for version, items in outcomes.items()}
    result = {"fixed_pass": fixed_pass, "detected_bug": detected,
              "unstable": any(len(set(items)) > 1 for items in statuses.values()),
              "statuses": statuses, "outcomes": outcomes,
              "coverage": "not_measured", "sandbox": "none-local-reviewed-diagnostic-only"}
    write_json(output / "evaluation.json", result)
    return result
