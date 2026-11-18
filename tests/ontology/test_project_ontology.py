"""Project ontology: syntactic facts, deterministic graph, grounded prompt views."""
from types import SimpleNamespace

import pytest

pytest.importorskip("rdflib")
pytest.importorskip("tree_sitter_java")

from llm_ontology import ontology  # noqa: E402
from llm_ontology.ontology.extract import JavaUnit  # noqa: E402
from llm_ontology.ontology.guards import ungrounded_names  # noqa: E402
from llm_ontology.ontology.views import CLOSE, OPEN, boundary_values  # noqa: E402

SRC = """public class Calc {
    private static final int LIMIT = 10;
    private int total;

    public static int clamp(int value, String label) {
        if (label == null) {
            throw new IllegalArgumentException("label");
        }
        if (value > LIMIT) {
            return LIMIT;
        }
        return value < 0 ? 0 : value;
    }

    public int add(int x) {
        int before = total;
        int sum = before + x;
        total = sum;
        for (int i = 0; i < x; i++) {
            if (i == 3) break;
        }
        return sum + before;
    }

    public void run() {
        add(clamp(3, "a"));
    }

    static String mode(int code) {
        switch (code) {
            case 1: return "one";
            default:
                if (code < 0) {
                    return "neg";
                } else {
                    throw new IllegalStateException("bad");
                }
        }
    }
}
"""


def method(unit, name):
    return unit.method_facts(next(m for m in unit.method_nodes() if unit.method_facts(m).name == name))


def test_throw_sites_list_every_enclosing_branch_not_a_firing_condition():
    unit = JavaUnit(SRC)
    clamp = method(unit, "clamp")
    assert [(t.exception, t.enclosing, t.earlier_exits, t.line) for t in clamp.throws] == [
        ("IllegalArgumentException", ("if label == null",), (), 7)]
    assert clamp.null_checks == ["label == null"]
    mode = method(unit, "mode")
    # "!(code < 0)" alone would be wrong: code == 1 returns earlier and never reaches the throw.
    assert [(t.enclosing, t.earlier_exits) for t in mode.throws] == [
        (("switch code default", "else of if code < 0"), (31, 34))]
    assert any(b.kind == "switch" and "cases: 1, default" in b.condition for b in mode.branches)


def test_throw_after_early_return_is_not_unconditional():
    src = "class A {\n  void f(int x) {\n    if (x > 0) return;\n    throw new IllegalStateException();\n  }\n}\n"
    (site,) = method(JavaUnit(src), "f").throws
    assert site.enclosing == () and site.earlier_exits == (3,)
    block = ontology.testing_view(src, "f")
    assert "enclosing branches: none; earlier return/throw at lines 3" in block
    assert "unconditionally" not in block and " when " not in block


def test_call_sites_are_by_name_and_flag_overloads():
    src = """import java.util.List;
class B {
    void add(int x) { }
    void add(String s) { }
    void run(List<Integer> list) {
        add(1);
        this.add("a");
        list.add(2);
    }
}
"""
    unit = JavaUnit(src)
    assert unit.call_sites("add") == [6, 7] and unit.overloads("add") == 2
    block = ontology.refactoring_view(src, "Rename Parameter", 3, 3)
    assert "by name (unqualified or this/super) at lines 6, 7; name has 2 declarations" in block
    assert ungrounded_names(block, src) == []


def test_extractor_comparisons_normalise_literal_side_and_constants():
    clamp = method(JavaUnit(SRC), "clamp")
    assert {(c.subject, c.operator, c.value) for c in clamp.comparisons} == {("value", ">", "LIMIT"), ("value", "<", "0")}


def test_block_facts_inputs_outputs_and_fields():
    facts = JavaUnit(SRC).block_facts(17, 18)
    assert {p.name for p in facts.inputs} == {"before", "x"}
    assert {p.name for p in facts.outputs} == {"sum"}
    assert facts.fields_written == ["total"] or set(facts.fields_written) == {"total"}
    assert not facts.has_return and not facts.has_jump
    loop = JavaUnit(SRC).block_facts(19, 21)
    assert loop.has_jump and not loop.has_return


def test_graph_is_deterministic_and_hashed():
    first = ontology.graph_ntriples(ontology.build_graph(SRC, block=(17, 18)))
    second = ontology.graph_ntriples(ontology.build_graph(SRC, block=(17, 18)))
    assert first == second and "urn:unit:" in first
    assert len(ontology.schema_sha256()) == 64


def test_testing_view_lists_only_supplied_facts():
    block = ontology.testing_view(SRC, "clamp", "Calc")
    assert block.startswith(OPEN) and block.endswith(CLOSE)
    assert "Focal method: public static int clamp(int value, String label) in Calc" in block
    assert "throw IllegalArgumentException at line 7; enclosing branches: if label == null" in block
    assert "value > LIMIT (= 10) -> try value = 10 / 11" in block
    assert "value < 0 -> try value = -1 / 0" in block
    assert "Reads fields: LIMIT : int = 10" in block
    assert ungrounded_names(block, SRC) == []
    with pytest.raises(ValueError):
        ontology.testing_view(SRC, "missing")


@pytest.mark.parametrize(("operation", "start", "end", "expected"), [
    ("Extract Method", 17, 18, ["read variables declared earlier: before : int, x : int",
                                "assign variables used after line 18: sum : int", "write fields: total"]),
    ("Rename Variable", 16, 16, ["Local before : int declared at line 16, initialised with total; used at lines 17, 22"]),
    ("Rename Parameter", 15, 15, ["Parameter x : int used at lines 17, 19",
                                  "Calls to add by name (unqualified or this/super) at lines 26"]),
    ("Rename Method", 15, 23, ["Method public int add(int x) spans lines 15..23; calls by name"]),
    ("Rename Class", 1, 40, ["Type Calc spans lines 1..40"]),
])
def test_refactoring_views(operation, start, end, expected):
    block = ontology.refactoring_view(SRC, operation, start, end)
    for text in expected:
        assert text in block
    assert ungrounded_names(block, SRC) == []
    assert block == ontology.refactoring_view(SRC, operation, start, end)


def test_case_helpers_and_leak_guard():
    case = SimpleNamespace(input_text=SRC, structured_identity={"class_name": "org.x.Calc", "method_name": "clamp"})
    block, identity = ontology.testing_context(case)
    assert "in Calc" in block and set(identity) == {"schema_version", "schema_sha256", "source_sha256",
                                                    "graph_sha256", "block_sha256"}
    with pytest.raises(ValueError, match="gold"):
        ontology.testing_context(case, forbidden=("label == null",))
    block, _ = ontology.refactoring_context({"before": SRC, "operation": "Extract Method",
                                             "target": {"start": 17, "end": 18}})
    assert "Lines 17..18" in block
    with pytest.raises(ValueError, match="absent"):
        ontology.assert_grounded(block + "\nrenamedHelper", SRC)


def test_boundary_values():
    assert boundary_values("<", "0") == ["-1", "0"]
    assert boundary_values("==", "0x10") == ["15", "16", "17"]
    assert boundary_values(">=", "size") == ["size"]


def test_block_depends_only_on_public_inputs():
    """Private reference data (gold tests, after code, expected tests) never changes the block bytes."""
    public = {"before": SRC, "operation": "Extract Method", "target": {"start": 17, "end": 18}}
    first, _ = ontology.refactoring_context({**public, "after": "class Calc { int helper() { return 1; } }",
                                             "expected_tests": ["a"]})
    second, _ = ontology.refactoring_context({**public, "after": "something else entirely",
                                              "expected_tests": ["b", "c"]})
    assert first == second
    base = {"class_name": "org.x.Calc", "method_name": "clamp"}
    a = SimpleNamespace(input_text=SRC, structured_identity=base, metadata={"reference": "assertEquals(10, x)"})
    b = SimpleNamespace(input_text=SRC, structured_identity=base, metadata={"reference": "other"})
    assert ontology.testing_context(a)[0] == ontology.testing_context(b)[0]


def test_locals_are_scoped_so_same_names_do_not_merge():
    src = """class C {
    void f(boolean a) {
        if (a) {
            String msg = "x";
            System.out.println(msg);
        } else {
            String msg = "y";
            System.out.println(msg + msg);
        }
        try { g(); } catch (IllegalStateException e) { h(e); }
    }
    void g() { }
    void h(Exception e) { }
    C make() { return new C(); }
}
"""
    unit = JavaUnit(src)
    node = next(m for m in unit.method_nodes() if unit.method_facts(m).name == "f")
    found = {(v.name, v.line): (v.type, v.uses) for v in unit.locals(node)}
    assert found[("msg", 4)] == ("String", [5]) and found[("msg", 7)] == ("String", [8])
    assert found[("e", 10)] == ("IllegalStateException", [10])
    assert unit.call_sites("C", constructor=True) == [14]


def test_request_orders_variables_and_cut_initialisers_keep_whole_names():
    long_init = "first.second().third(" + ", ".join(f"argumentNumber{i}" for i in range(8)) + ")"
    decls = "\n".join(f"        int v{i} = {i};" for i in range(9))
    src = f"class D {{\n    int f(Helper first) {{\n{decls}\n        int target = {long_init};\n" \
          f"        return target + v0;\n    }}\n}}\n"
    block = ontology.refactoring_view(src, "Inline Variable", 3, 12, request="Inline Variable target : int")
    variable_lines = [line for line in block.splitlines() if line.startswith("Local ")]
    assert variable_lines[0].startswith("Local target : int declared at line 12, initialised with first.second()")
    assert "..." in variable_lines[0] and "(+4 more variables declared in lines 3..12)" in block
    assert ungrounded_names(block, src) == []
