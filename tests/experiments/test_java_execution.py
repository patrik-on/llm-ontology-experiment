"""Dataset-independent Jupiter evaluator regression checks."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from llm_ontology.benchmarks.java_execution import clean_env, evaluate_revision, java_identity, read_jupiter_reports

def test_java_identity_ignores_comments_and_strings():
    source = '// class Fake {}\npackage a.b; class Real { String s="class Fake {}"; }'
    assert java_identity(source) == ("Real", "a.b.Real")
    with pytest.raises(ValueError, match="Exactly one"):
        java_identity("class A {} class B {}")
    with pytest.raises(ValueError):
        java_identity("// class Fake {}")

@pytest.mark.parametrize(("body", "status", "executed"), [
    ("", "no_tests", 0),
    ('<testcase classname="Probe" name="x"/>', "passed", 1),
    ('<testcase classname="Probe" name="x"><skipped/></testcase>', "no_tests", 0),
    ('<testcase classname="Other" name="x"/>', "no_tests", 0),
    ('<testcase classname="Probe" name="x"><failure type="org.opentest4j.AssertionFailedError"/></testcase>', "assertion_failure", 1),
    ('<testcase classname="Probe" name="x"><failure type="java.lang.RuntimeException"/></testcase>', "execution_error", 1),
    ('<testcase classname="Probe" name="x"><error/></testcase>', "execution_error", 1),
])
def test_positive_fresh_discovery(tmp_path, body, status, executed):
    (tmp_path / "TEST-junit-jupiter.xml").write_text(f'<testsuite tests="999">{body}</testsuite>')
    result = read_jupiter_reports(tmp_path, "Probe")
    assert result["status"] == status
    assert result["executed"] == executed

def test_malformed_report_is_infrastructure(tmp_path):
    (tmp_path / "TEST-junit-jupiter.xml").write_text("<bad")
    assert read_jupiter_reports(tmp_path, "Probe")["status"] == "infrastructure_error"

def test_environment_does_not_inherit_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "secret")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-javaagent:bad.jar")
    env = clean_env(tmp_path / "home", Path("/jdk"))
    assert "HF_TOKEN" not in env
    assert "JAVA_TOOL_OPTIONS" not in env
    assert "SSH_AUTH_SOCK" not in env
    assert env["TZ"] == "America/Los_Angeles"

def test_stale_work_directory_and_jar_mismatch_rejected(tmp_path):
    jar = tmp_path / "junit.jar"
    jar.write_bytes(b"bad")
    with pytest.raises(ValueError, match="checksum"):
        evaluate_revision("class Probe {}", {}, output=tmp_path / "run", java_home=tmp_path,
                          junit_jar=jar, junit_sha256="0"*64)
    from llm_ontology.benchmarks.java_execution import file_sha256
    with pytest.raises(FileExistsError):
        evaluate_revision("class Probe {}", {}, output=tmp_path, java_home=tmp_path,
                          junit_jar=jar, junit_sha256=file_sha256(jar))

def test_nonindexable_manifest_contract():
    from llm_ontology.ingestion.manifest import DatasetManifest
    manifest = DatasetManifest(dataset_name="java-evaluator-control", source_path="x", source_split="active",
                               usage_role="benchmark", allowed_for_indexing=False, content_hash="a")
    with pytest.raises(ValueError, match="forbids indexing"):
        manifest.require_indexable()



def test_run_id_path_traversal_rejected():
    from llm_ontology.evaluation.run_layout import EvaluationRunLayout
    with pytest.raises(ValueError):
        EvaluationRunLayout("../../bad")

def test_model_description_uses_existing_provider_transport():
    from llm_ontology.inference.ollama_client import OllamaProvider
    captured = {}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b'{"details":{"quantization_level":"Q4_K_M"},"template":"template"}'
    def opener(request, **kwargs):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return Response()
    provider = OllamaProvider(model_name="local", opener=opener)
    result = provider.describe_model()
    assert captured == {"url": "http://localhost:11434/api/show", "body": {"model": "local"}}
    assert result["details"]["quantization_level"] == "Q4_K_M"

def test_shared_hf_loader_explicit_local_only_preserves_defaults(monkeypatch):
    import sys
    from types import SimpleNamespace
    from llm_ontology.benchmarks.evaluation_generation import load_eval_model
    captured = {}
    tokenizer = SimpleNamespace(pad_token="pad", eos_token="eos")
    model = SimpleNamespace(eval=lambda: None)
    class Tokenizer:
        @staticmethod
        def from_pretrained(path, **kwargs):
            captured["tokenizer"] = kwargs
            return tokenizer
    class Model:
        @staticmethod
        def from_pretrained(path, **kwargs):
            captured["model"] = kwargs
            return model
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=Tokenizer, AutoModelForCausalLM=Model, BitsAndBytesConfig=object))
    load_eval_model({"model_path": "/local"}, {"local_files_only": True, "trust_remote_code": False})
    for key in ("tokenizer", "model"):
        assert captured[key]["local_files_only"] is True
        assert captured[key]["trust_remote_code"] is False
    load_eval_model({"model_path": "/local"}, {})
    assert captured["model"]["trust_remote_code"] is True
    assert captured["model"]["local_files_only"] is False

@pytest.mark.skipif(__import__('os').name != 'posix', reason="Linux process groups")
def test_timeout_terminates_children_in_original_process_group(tmp_path):
    import sys
    from llm_ontology.benchmarks.java_execution import run_process
    command = [sys.executable, "-c", "import subprocess,sys,time; "
               "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
               "print(p.pid,flush=True); time.sleep(30)"]
    result = run_process(command, tmp_path, clean_env(tmp_path / "home", Path("/jdk")),
                         1, tmp_path / "process.log")
    assert result["status"] == "timeout"
    child = (tmp_path / "process.log").read_text().strip()
    stat = Path(f"/proc/{child}/stat")
    assert not stat.exists() or stat.read_text().split()[2] == "Z"
