import pytest
from llm_ontology.benchmarks.methods2test_selection import infer_spec, words
from llm_ontology.benchmarks.methods2test_selection import general_wrap_record as wrap_record


def record(
    focal="public static int twice(int x) { return x * FACTOR; }",
    gold="@Test public void testTwice() { assertEquals(4, Example.twice(2)); }",
):
    return {
        "focal_method": {"body": focal, "identifier": "twice"},
        "test_case": {"body": gold},
        "focal_class": {
            "identifier": "Example",
            "file": "module/src/main/java/org/example/Example.java",
            "fields": [
                {"var_name": "FACTOR", "original_string": "static final int FACTOR = 2;"},
                {"var_name": "LOGGER", "original_string": "Unknown LOGGER;"},
            ],
        },
        "test_class": {},
    }


def test_verbatim_only_needed_fields():
    d = record()
    spec = infer_spec(d)
    prod, ref, policy = wrap_record({"raw": d}, spec)
    assert d["focal_method"]["body"] in prod
    assert d["test_case"]["body"] in ref
    assert spec["fields"] == ["FACTOR"]
    assert "LOGGER" not in prod
    assert policy["method_logic"] == "verbatim"


@pytest.mark.parametrize(
    "gold",
    [
        "@Test(expected=Exception.class) public void t() {}",
        "@Test @Disabled public void t() {}",
        "@ParameterizedTest void t() {}",
    ],
)
def test_no_annotation_conversion(gold):
    with pytest.raises(ValueError, match="non_simple_test_annotation"):
        infer_spec(record(gold=gold))


def test_no_effectful_source():
    with pytest.raises(ValueError, match="effects"):
        infer_spec(record("public static int twice(int x) { System.exit(0); return x; }"))


def test_literals_not_dependencies():
    assert words('String text = "System File LOGGER"; // Runtime\n int x;') == {
        "String",
        "text",
        "int",
        "x",
    }


def test_assertion_binding_and_explicit_jdk_import():
    d = record(
        gold="@Test public void testTwice() { List<Integer> x = new ArrayList<>(); assertThat(Example.twice(2)).isEqualTo(4); }"
    )
    spec = infer_spec(d)
    assert spec["assertions"] == "assertj"
    assert spec["imports"] == []
    assert spec["reference_imports"] == ["java.util.ArrayList", "java.util.List"]
    production, reference, _ = wrap_record({"raw": d}, spec)
    assert "import java.util.List" not in production
    assert "import java.util.List" in reference


def test_deny_inherited_semantics():
    d = record()
    d["test_class"]["superclass"] = "BaseFixture"
    with pytest.raises(ValueError, match="inheritance"):
        infer_spec(d)


@pytest.mark.parametrize(
    "body",
    [
        'public static int twice(int x) throws Exception { new java.net.URL("https://example.com").openStream(); return x; }',
        'public static int twice(int x) throws Exception { new java.io.PrintWriter("x").close(); return x; }',
    ],
)
def test_effectful_fully_qualified_apis_rejected(body):
    with pytest.raises(ValueError, match="effects"):
        infer_spec(record(focal=body))


@pytest.mark.parametrize("name", ["Date", "Optional", "Predicate"])
def test_ambiguous_bindings_rejected(name):
    with pytest.raises(ValueError, match="ambiguous_JDK"):
        infer_spec(record(focal="public static " + name + " twice(int x) { return null; }"))


def test_implicit_original_constructor_not_fabricated():
    with pytest.raises(ValueError, match="constructor_semantics"):
        infer_spec(record(focal="public static Example twice(int x) { return new Example(); }"))


def test_resume_preserves_own_ids_and_excludes_historical(tmp_path, monkeypatch):
    import json
    from llm_ontology.benchmarks.methods2test_selection import historical_selection_ids

    monkeypatch.chdir(tmp_path)
    root = tmp_path / "artifacts/evaluation/runs/current"
    root.mkdir(parents=True)
    (root / "selection.json").write_text(json.dumps({"ids": ["current_case"]}))
    other = root.parent / "old"
    other.mkdir()
    (other / "selection.json").write_text(json.dumps({"ids": ["old_case"]}))
    config = tmp_path / "configs/benchmarks/testing_matrix_v1.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"prior_explored_case_ids": ["archived_case"]}))
    assert historical_selection_ids(root) == {"old_case", "archived_case"}
