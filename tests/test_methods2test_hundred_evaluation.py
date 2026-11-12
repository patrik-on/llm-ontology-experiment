import json
import pytest
from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test_hundred_evaluation import review


def setup(root, text):
    write_json(root / "selection.json", {"ids": ["one"]})
    out = root / "cases/one/predictions/qwen_base"
    out.mkdir(parents=True)
    p = out / "generated.java"
    p.write_text(text)
    write_json(out / "generation.json", {"source_sha256": file_sha256(p)})
    return out


def test_review_hash_binds_verbatim_source(tmp_path):
    text = "class GeneratedBodyTests { void t() { assertEquals(2, Subject.f(1)); } }"
    out = setup(tmp_path, text)
    pins = review(tmp_path)
    assert pins["one/qwen_base"] == file_sha256(out / "generated.java")
    assert (out / "generated.java").read_text() == text


def test_review_rejects_effects_without_repair(tmp_path):
    text = "class GeneratedBodyTests { void t() { System.exit(0); } }"
    out = setup(tmp_path, text)
    assert review(tmp_path) == {}
    m = json.loads((out / "metrics.json").read_text())
    assert m["coverage"] is None and not m["class_pass"]
    assert "source_review_rejected" in m["coverage_reason"]
    assert (out / "generated.java").read_text() == text


def test_review_does_not_rebind_modified_candidate(tmp_path):
    out = setup(tmp_path, "class GeneratedBodyTests {}")
    (out / "generated.java").write_text("class Changed {}")
    with pytest.raises(ValueError, match="candidate_bytes_changed"):
        review(tmp_path)


@pytest.mark.parametrize(
    "call",
    [
        'new java.net.URL("https://example.com").openStream();',
        'new java.io.PrintWriter("x").close();',
    ],
)
def test_fully_qualified_effectful_sources_not_executed(tmp_path, call):
    out = setup(tmp_path, "class GeneratedBodyTests { void t() throws Exception { " + call + " } }")
    assert review(tmp_path) == {}
    assert json.loads((out / "metrics.json").read_text())["statuses"] == ["source_review_rejected"]
