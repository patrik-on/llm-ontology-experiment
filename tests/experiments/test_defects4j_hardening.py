from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_ontology.benchmarks.defects4j import (
    D4J_COMMIT, Defects4JConfig, validate_subject_selection,
)
from llm_ontology.benchmarks.defects4j_execution import read_console_summary
from llm_ontology.benchmarks.defects4j_runner import canary, lang24_fault_control_applicable


def config(tmp_path, **kwargs):
    return Defects4JConfig(defects4j_home=tmp_path, java_home=tmp_path, work_root=tmp_path,
                          junit_jar=tmp_path, junit_sha256="0"*64, **kwargs)


def math_config(tmp_path, **kwargs):
    return config(tmp_path, project="Math", bug_id=kwargs.pop("bug_id", 1),
                  focal_class="org.apache.commons.math3.util.MathUtils", focal_method="normalizeAngle",
                  repository_markers=["commons-math"], hf_model_name="configured_local_adapter", **kwargs)


def test_configurable_case_and_adapter_keep_defaults(tmp_path):
    selected = math_config(tmp_path)
    assert selected.case_id == "Math-1"
    assert selected.hf_model_name == "configured_local_adapter"
    assert not lang24_fault_control_applicable(selected)
    assert lang24_fault_control_applicable(config(tmp_path))
    assert not lang24_fault_control_applicable(config(tmp_path, bug_id=25))
    assert not lang24_fault_control_applicable(config(tmp_path, focal_method="createNumber"))


@pytest.mark.parametrize("values", [
    {"project": "../Lang"}, {"bug_id": 0}, {"bug_id": -1},
    {"focal_class": "a..b"}, {"focal_class": "../../Secret"},
    {"focal_class": "a/B"}, {"focal_method": "x();"}, {"hf_model_name": ""},
    {"validation_sources": []}, {"checkpoint_selection_sources": []},
    {"repository_markers": []}, {"project": "Math"},
])
def test_invalid_selections_are_rejected(tmp_path, values):
    with pytest.raises(ValidationError):
        config(tmp_path, **values)


def test_active_case_metadata_and_pin_are_required(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j as module
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: D4J_COMMIT)
    selected = math_config(tmp_path)
    directory = tmp_path / "framework/projects/Math"
    directory.mkdir(parents=True)
    metadata = directory / "active-bugs.csv"
    metadata.write_text('bug.id,revision.id.buggy,revision.id.fixed\n1,old,new\n')
    result = validate_subject_selection(selected)
    assert result["active_bug_row"] == ["1", "old", "new"]
    assert result["project"] == "Math"
    with pytest.raises(ValueError, match="active bug"):
        validate_subject_selection(math_config(tmp_path, bug_id=2))
    metadata.write_text('1,a,b\n1,c,d\n')
    with pytest.raises(ValueError, match="unique active"):
        validate_subject_selection(selected)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "wrong")
    with pytest.raises(ValueError, match="pinned"):
        validate_subject_selection(selected)


def test_missing_project_not_implicitly_downloaded(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j as module
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: D4J_COMMIT)
    with pytest.raises(ValueError, match="unavailable"):
        validate_subject_selection(math_config(tmp_path))


def test_other_case_generic_controls_never_execute_lang24_reference(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j_runner as module
    expected = {"pass": "passed", "assertion": "assertion_failure", "empty": "no_tests",
                "disabled": "no_tests", "compile": "compile_failure", "runtime": "execution_error",
                "before_all_runtime": "container_failure", "before_all_assertion": "container_failure",
                "aborted": "test_aborted", "abnormal_shutdown": "infrastructure_error", "timeout": "timeout"}
    def fake(source, revision, **kwargs):
        assert "Lang24Canary" not in source
        return {"status": expected[kwargs["output"].name]}
    monkeypatch.setattr(module, "evaluate_revision", fake)
    def forbidden(*args, **kwargs):
        pytest.fail("Lang24 reference cannot be executed for another case")
    monkeypatch.setattr(module, "evaluate_pair", forbidden)
    result = canary(math_config(tmp_path), {"fixed": {}, "case_sha256": "case"}, tmp_path / "controls")
    assert result["passed"] and result["generic_controls_passed"]
    assert result["real_fault_detected"] is None
    assert result["fault_validation_status"] == "not_validated_for_case"
    assert not result["known_fault_control_applicable"]


def summary(**overrides):
    fields = {"tests found": 1, "tests skipped": 0, "tests started": 1, "tests aborted": 0,
              "tests successful": 1, "tests failed": 0, "containers failed": 0}
    fields.update(overrides)
    return "\n".join(f"[{number:10} {name:20}]" for name, number in fields.items())


def test_summary_is_positive_and_failclosed():
    assert read_console_summary(summary())["tests_started"] == 1
    assert read_console_summary(summary(**{"tests started": 0, "containers failed": 1}))["tests_started"] == 0
    with pytest.raises(ValueError):
        read_console_summary(summary() + "\n[1 tests started]")
    with pytest.raises(ValueError):
        read_console_summary("no summary")


def test_abort_summary_is_not_a_success_count():
    result = read_console_summary(summary(**{"tests aborted": 1, "tests successful": 0}))
    assert result["tests_started"] - result["tests_aborted"] == 0


def test_changed_implementation_cannot_rewrite_historical_run(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j_runner as module
    from llm_ontology.evaluation.run_layout import EvaluationRunLayout
    monkeypatch.chdir(tmp_path)
    rag = tmp_path / "rag.yaml"
    hf = tmp_path / "hf.yaml"
    rag.write_text("existing config")
    hf.write_text("existing model config")
    selected = config(tmp_path, retrieval_config=rag, hf_models_config=hf)
    monkeypatch.setattr(module, "load_config", lambda path: selected)
    monkeypatch.setattr(module, "require_wsl", lambda: None)
    layout = EvaluationRunLayout("historical-run")
    layout.write_manifest(status="diagnostic_completed", metadata={"config": {"old": True}, "dependencies": {}})
    before = layout.manifest_path.read_bytes()
    with pytest.raises(ValueError, match="Run/config mismatch"):
        module.main(["audit", "--run-id", "historical-run"])
    assert layout.manifest_path.read_bytes() == before


def test_missing_validation_or_checkpoint_source_fails_closed(tmp_path):
    # Configuration cannot silently omit either source role.
    with pytest.raises(ValidationError):
        config(tmp_path, validation_sources=[])
    with pytest.raises(ValidationError):
        config(tmp_path, checkpoint_selection_sources=[])


def test_malformed_xml_is_not_downgraded_to_no_tests(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j_execution as module
    jar = tmp_path / "junit.jar"
    jar.write_bytes(b"fixture")
    out = tmp_path / "run"
    def fake(command, cwd, env, timeout, log):
        if log.name == "execution.log":
            (out / "reports/TEST-junit-jupiter.xml").write_text("<malformed")
            log.write_text(summary(**{"tests found": 0, "tests started": 0, "tests successful": 0}))
            return {"status": "completed", "returncode": 2}
        log.write_text("compiled fixture")
        return {"status": "completed", "returncode": 0}
    monkeypatch.setattr(module, "run_process", fake)
    result = module.evaluate_revision("class Probe {}", {"bin_classes": str(tmp_path), "dependencies": []},
                                     output=out, java_home=tmp_path, junit_jar=jar,
                                     junit_sha256=module.file_sha256(jar))
    assert result["status"] == "infrastructure_error"
