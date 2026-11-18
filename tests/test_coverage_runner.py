"""Model-free JaCoCo tests. Real canaries use existing local pinned jars only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

from llm_ontology.benchmarks import java_execution as shared
from llm_ontology.evaluation import coverage_runner as coverage


def report(tmp_path, *, branch=True):
    root = ET.Element("report")
    package = ET.SubElement(root, "package", name="demo")
    cls = ET.SubElement(package, "class", name="demo/Subject")
    method = ET.SubElement(cls, "method", name="classify", desc="(I)I")
    for node in (cls, method):
        for kind, missed, covered in (("LINE", 1, 2), ("METHOD", 0, 1)):
            ET.SubElement(node, "counter", type=kind, missed=str(missed), covered=str(covered))
        if branch:
            ET.SubElement(node, "counter", type="BRANCH", missed="1", covered="1")
    xml = tmp_path / "jacoco.xml"
    ET.ElementTree(root).write(xml)
    return root, cls, method, xml


def save_read(root, xml, method="classify", cls="demo.Subject"):
    ET.ElementTree(root).write(xml)
    return coverage.read_jacoco_xml(xml, cls, method)


def test_real_counters_and_focal_invocation(tmp_path):
    root, cls, method, xml = report(tmp_path)
    result = save_read(root, xml)
    assert result["status"] == "measured" and result["focal_invoked"] is True
    assert result["method"]["counters"]["line"]["ratio"] == 2 / 3
    assert result["class"]["counters"]["branch"]["ratio"] == 0.5
    count = next(c for c in method.findall("counter") if c.get("type") == "METHOD")
    count.set("missed", "1")
    count.set("covered", "0")
    assert save_read(root, xml)["focal_invoked"] is False


def test_absent_branch_and_zero_branch_are_null_not_perfect(tmp_path):
    root, cls, method, xml = report(tmp_path, branch=False)
    result = save_read(root, xml)
    assert result["status"] == "measured"
    for scope in ("class", "method"):
        assert result[scope]["counters"]["branch"] == {
            "missed": None, "covered": None, "total": None, "ratio": None,
            "reason": "missing_counter"}
    for node in (cls, method):
        ET.SubElement(node, "counter", type="BRANCH", missed="0", covered="0")
    result = save_read(root, xml)
    assert result["method"]["counters"]["branch"]["ratio"] is None
    assert result["method"]["counters"]["branch"]["reason"] == "zero_total"


@pytest.mark.parametrize("scope,kind", [("class", "LINE"), ("class", "METHOD"),
                                         ("method", "LINE"), ("method", "METHOD")])
def test_missing_required_counter_fails_closed(tmp_path, scope, kind):
    root, cls, method, xml = report(tmp_path)
    node = cls if scope == "class" else method
    node.remove(next(c for c in node.findall("counter") if c.get("type") == kind))
    result = save_read(root, xml)
    assert result["status"] != "measured"
    assert result[scope]["counters"][kind.lower()]["ratio"] is None


@pytest.mark.parametrize("change", ["negative", "noninteger", "duplicate", "zero_method"])
def test_invalid_counters_fail_closed(tmp_path, change):
    root, cls, method, xml = report(tmp_path)
    counter = next(c for c in method.findall("counter") if c.get("type") == "METHOD")
    if change == "duplicate":
        ET.SubElement(method, "counter", **counter.attrib)
    else:
        counter.set("covered", {"negative": "-1", "noninteger": "x", "zero_method": "0"}[change])
    result = save_read(root, xml)
    assert result["status"] != "measured" and result["focal_invoked"] is None


def test_missing_class_method_and_ambiguous_overload(tmp_path):
    root, cls, method, xml = report(tmp_path)
    assert save_read(root, xml, cls="other.Subject")["reason"] == "missing_class"
    assert save_read(root, xml, method="absent")["reason"] == "missing_method"
    second = ET.SubElement(cls, "method", name="classify", desc="()I")
    for count in method.findall("counter"):
        ET.SubElement(second, "counter", **count.attrib)
    assert save_read(root, xml)["reason"] == "ambiguous_method"
    assert save_read(root, xml, method="classify(I)I")["status"] == "measured"


def test_malformed_or_missing_xml(tmp_path):
    xml = tmp_path / "missing.xml"
    assert coverage.read_jacoco_xml(xml, "demo.Subject", "classify")["reason"] == "invalid_or_missing_xml"
    xml.write_text("<bad>")
    assert coverage.read_jacoco_xml(xml, "demo.Subject", "classify")["focal_invoked"] is None


def test_artifact_pins_match_config():
    config = json.loads((Path(__file__).parents[1] / "configs/evaluation/jacoco_v1.json").read_text())
    assert config["artifacts"]["agent"]["sha256"] == coverage.AGENT_SHA256
    assert config["artifacts"]["cli"]["sha256"] == coverage.CLI_SHA256
    assert config["version"] == coverage.JACOCO_VERSION


def test_java_options_hook_is_execution_only_and_default_unchanged(tmp_path, monkeypatch):
    commands = []
    def fake(command, cwd, env, timeout, log):
        commands.append(command)
        log.write_text("fixture")
        return {"status": "completed", "returncode": 0}
    monkeypatch.setattr(shared, "run_process", fake)
    jar = tmp_path / "junit.jar"
    jar.write_bytes(b"fixture")
    for name, options in (("default", None), ("agent", ["-javaagent:reviewed.jar"])):
        shared.evaluate_revision("class Probe {}", {"bin_classes": str(tmp_path), "dependencies": []},
                                 output=tmp_path / name, java_home=tmp_path, junit_jar=jar,
                                 junit_sha256=shared.file_sha256(jar), java_options=options)
    assert not any("-javaagent:" in arg for arg in commands[0] + commands[1] + commands[2])
    assert commands[3][2:4] == ["-javaagent:reviewed.jar", "-jar"]


@pytest.fixture(scope="module")
def toolchain():
    work = Path(os.environ.get("BENCHMARK_WORK", "/home/patrik/benchmark-work"))
    values = {"java_home": work / "deps/jdk-11.0.33+10",
              "junit_jar": work / "downloads/junit-platform-console-standalone-1.11.4.jar",
              "agent_jar": work / "downloads/org.jacoco.agent-0.8.13-runtime.jar",
              "cli_jar": work / "downloads/org.jacoco.cli-0.8.13-nodeps.jar"}
    if os.name != "posix" or not all(p.exists() for p in values.values()):
        pytest.skip("Real coverage canary requires the existing local WSL benchmark toolchain")
    values["junit_sha256"] = shared.file_sha256(values["junit_jar"])
    return values


@pytest.fixture
def production(tmp_path, toolchain):
    source = tmp_path / "Subject.java"
    source.write_text("""package demo;
public class Subject {
  public static int classify(int x) {
    if (x > 0) {
      return 1;
    }
    return -1;
  }
  public static int unrelated() { return 7; }
}
""")
    classes = tmp_path / "production"
    classes.mkdir()
    subprocess.run([str(toolchain["java_home"] / "bin/javac"), "-g", "-proc:none", "-d",
                    str(classes), str(source)], check=True, capture_output=True)
    return {"bin_classes": str(classes), "dependencies": []}


def run_canary(tmp_path, production, toolchain, body, **kwargs):
    source = """import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
public class Probe {
""" + body + "\n}\n"
    return coverage.run_jacoco_coverage(source, production, output=tmp_path / "coverage",
                                        focal_class="demo.Subject", focal_method="classify",
                                        **toolchain, **kwargs)


@pytest.mark.parametrize("body,invoked,branch", [
    ("@Test void one() { assertEquals(1, demo.Subject.classify(3)); }", True, 0.5),
    ("@Test void both() { assertEquals(1, demo.Subject.classify(3)); "
     "assertEquals(-1, demo.Subject.classify(-2)); }", True, 1.0),
    ("@Test void unrelated() { assertEquals(7, demo.Subject.unrelated()); }", False, 0.0),
    ("@Test void neverLoads() { assertTrue(true); }", False, 0.0),
])
def test_real_branch_and_noninvocation_canaries(tmp_path, production, toolchain, body, invoked, branch):
    result = run_canary(tmp_path, production, toolchain, body)
    assert result["status"] == "passed", result
    assert result["coverage_status"] == "measured", result
    assert result["focal_invoked"] is invoked
    assert result["coverage"]["method"]["counters"]["branch"]["ratio"] == branch
    assert result["diagnostic_coverage"] is None
    root = ET.parse(result["xml"]["path"]).getroot()
    assert [c.get("name") for c in root.findall("./package/class")] == ["demo/Subject"]
    persisted = json.loads((tmp_path / "coverage/coverage.json").read_text())
    assert persisted["focal_invoked"] is invoked


@pytest.mark.parametrize("body,status", [
    ("@Test void wrong() { assertEquals(99, demo.Subject.classify(1)); }", "assertion_failure"),
    ("void noTests() { demo.Subject.classify(1); }", "no_tests"),
    ("@Test void broken() { noSuchMethod(); }", "compile_failure"),
])
def test_real_failed_and_empty_are_not_success_metrics(tmp_path, production, toolchain, body, status):
    result = run_canary(tmp_path, production, toolchain, body)
    assert result["status"] == status
    assert result["coverage"] is None and result["focal_invoked"] is None
    if status == "assertion_failure":
        assert result["coverage_status"] == "diagnostic_only"
        assert result["diagnostic_coverage"]["focal_invoked"] is True
    if status == "compile_failure":
        assert result["coverage_reason"] == "missing_execution_data"


def test_pins_and_production_shadow_rejected(tmp_path, production, toolchain):
    bad = tmp_path / "bad.jar"
    bad.write_bytes(b"not the pinned artifact")
    with pytest.raises(ValueError, match="checksum"):
        coverage.run_jacoco_coverage("class Probe {}", production, output=tmp_path / "bad",
                                    focal_class="demo.Subject", focal_method="classify",
                                    **{**toolchain, "agent_jar": bad})
    with pytest.raises(ValueError, match="shadow"):
        coverage.run_jacoco_coverage("package demo; public class Subject {}", production,
                                    output=tmp_path / "shadow", focal_class="demo.Subject",
                                    focal_method="classify", **toolchain)
    assert not (tmp_path / "shadow").exists()


def test_real_no_debug_lines_is_not_invented_zero(tmp_path, production, toolchain):
    subprocess.run([str(toolchain["java_home"] / "bin/javac"), "-g:none", "-proc:none", "-d",
                    production["bin_classes"], str(tmp_path / "Subject.java")],
                   check=True, capture_output=True)
    result = run_canary(tmp_path, production, toolchain,
                        "@Test void run() { assertEquals(1, demo.Subject.classify(1)); }")
    assert result["status"] == "passed" and result["coverage_status"] == "incomplete"
    assert result["coverage"] is None
    assert result["diagnostic_coverage"]["class"]["counters"]["line"]["ratio"] is None


@pytest.mark.parametrize("mode,reason", [
    ("report_failure", "report_failed"),
    ("mismatch", "execution_class_mismatch"),
    ("changed", "production_class_changed"),
    ("missing_xml", "invalid_or_missing_xml"),
    ("missing_exec", "missing_execution_data"),
])
def test_report_pipeline_fails_closed(tmp_path, monkeypatch, mode, reason):
    jar = tmp_path / "fixture.jar"
    jar.write_bytes(b"reviewed fixture")
    digest = shared.file_sha256(jar)
    monkeypatch.setattr(coverage, "AGENT_SHA256", digest)
    monkeypatch.setattr(coverage, "CLI_SHA256", digest)
    cls = tmp_path / "production/demo/Subject.class"
    cls.parent.mkdir(parents=True)
    cls.write_bytes(b"original production")
    output = tmp_path / "run"
    def fake_evaluate(source, revision, **kwargs):
        assert kwargs["java_options"][0].startswith("-javaagent:")
        if mode != "missing_exec":
            (output / "jacoco.exec").write_bytes(b"execution fixture")
        if mode == "changed":
            cls.write_bytes(b"changed production")
        return {"status": "passed"}
    def fake_report(command, cwd, env, timeout, log):
        # No classes directory, dependency tree or generated tests can be reported.
        assert command[command.index("--classfiles") + 1] == str(cls)
        log.write_text("Execution data does not match" if mode == "mismatch" else "fixture")
        return {"status": "completed", "returncode": 1 if mode == "report_failure" else 0}
    monkeypatch.setattr(coverage, "evaluate_revision", fake_evaluate)
    monkeypatch.setattr(coverage, "run_process", fake_report)
    result = coverage.run_jacoco_coverage(
        "class Probe {}", {"bin_classes": str(tmp_path / "production"), "dependencies": []},
        output=output, java_home=tmp_path, junit_jar=jar, junit_sha256=digest,
        agent_jar=jar, cli_jar=jar, focal_class="demo.Subject", focal_method="classify")
    assert result["status"] == "passed"  # Class correctness != coverage measurement success.
    assert result["coverage_reason"] == reason
    assert result["coverage"] is None and result["focal_invoked"] is None
    with pytest.raises(FileExistsError):
        coverage.run_jacoco_coverage(
            "class Probe {}", {"bin_classes": str(tmp_path / "production"), "dependencies": []},
            output=output, java_home=tmp_path, junit_jar=jar, junit_sha256=digest,
            agent_jar=jar, cli_jar=jar, focal_class="demo.Subject", focal_method="classify")


def test_real_no_branch_method_stays_null(tmp_path, production, toolchain):
    result = coverage.run_jacoco_coverage(
        "import org.junit.jupiter.api.Test; public class Probe { "
        "@Test void run() { demo.Subject.unrelated(); } }", production,
        output=tmp_path / "coverage", focal_class="demo.Subject", focal_method="unrelated",
        **toolchain)
    assert result["status"] == "passed" and result["focal_invoked"] is True
    branch = result["coverage"]["method"]["counters"]["branch"]
    assert branch["ratio"] is None and branch["reason"] == "missing_counter"
