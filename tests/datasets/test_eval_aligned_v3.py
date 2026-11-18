"""v3 FT records must be byte-identical to what the matrices send their FT arms and
their gold outputs must pass the matrices' own strict parsers."""
import json

import pytest

from llm_ontology.benchmarks import refactoring_execution as ex
from llm_ontology.benchmarks.matrix_support import ft_case
from llm_ontology.benchmarks.refactoring_matrix import render
from llm_ontology.datasets import eval_aligned_v3 as v3
from llm_ontology.inference.prompting import testing_bodies_v1 as v1
from llm_ontology.inference.prompting.instruction import format_inference_prompt, format_prompt
from llm_ontology.inference.structured_output import parse_testing_bodies


def raw(gold, repo_id=7, method="twice", file="module/src/main/java/org/example/Example.java"):
    return {
        "repository": {"repo_id": repo_id, "url": f"https://github.com/o/p{repo_id}"},
        "focal_method": {"body": f"public static int {method}(int x) {{ return x * FACTOR; }}",
                         "identifier": method, "full_signature": f"public static int {method}(int x)"},
        "test_case": {"body": gold, "identifier": "t"},
        "focal_class": {"identifier": "Example", "file": file,
                        "fields": [{"var_name": "FACTOR", "original_string": "static final int FACTOR = 2;"}]},
        "test_class": {"fields": [{"var_name": "fixture"}]},
    }


GOLD1 = "@Test public void testTwice() {\n    assertEquals(4, Example.twice(2));\n}"
GOLD2 = "@Test public void testZero() throws Exception {\n    Assert.assertEquals(0, Example.twice(0));\n}"


def test_testing_record_matches_ft_testing_prompt_and_parses():
    first, second = v3.testing_candidate(raw(GOLD1)), v3.testing_candidate(raw(GOLD2))
    record = v3.testing_record(first, second, "a+b")
    # Exactly the testing_matrix freeze path: format_inference_prompt(ft_case(case).instruction, input).
    case = v3.testing_case(first, "a+b")
    assert format_prompt(record) == format_inference_prompt(ft_case(case).instruction, case.input_text)
    assert "JSON schema" in record["instruction"] and "BEGIN UNRELATED SOLVED BODY" in record["instruction"]
    answer = parse_testing_bodies(record["output"])
    assert answer.testCase1 == "assertEquals(4, Example.twice(2));"
    assert answer.testCase2 == "assertEquals(0, Example.twice(0));"  # Assert. prefix mapped
    source = v1.assemble(v1.scaffold(case), answer)
    assert "@Test void testCase2" in source and "Example.twice(0)" in source


@pytest.mark.parametrize("gold, reason", [
    ('@Test public void t() { assertEquals("msg", 4, Example.twice(2)); }', "junit4_message_first"),
    ('@Test public void t() { assertTrue("msg", Example.twice(2) == 4); }', "junit4_message_first"),
    ("@Test public void t() { assertThat(Example.twice(2)).isEqualTo(4); }", "jupiter_scaffold"),
    ("@Test public void t() { assertEquals(fixture, Example.twice(2)); }", "test_class_members"),
])
def test_testing_candidate_rejects_bodies_the_scaffold_cannot_hold(gold, reason):
    with pytest.raises(ValueError, match=reason):
        v3.testing_candidate(raw(gold))


def test_string_expected_value_is_not_mistaken_for_a_message():
    body = v3.jupiter_compatible_body('assertEquals("a,b", Example.join("a", "b"));')
    assert body.startswith("assertEquals(")


def test_pairs_need_two_distinct_tests_of_one_focal_method_and_respect_project_cap():
    a, b = v3.testing_candidate(raw(GOLD1)), v3.testing_candidate(raw(GOLD2))
    lone = v3.testing_candidate(raw(GOLD1.replace("twice", "thrice"), method="thrice"))
    pairs = v3.pair_testing_candidates([a, b, a, lone], project_cap=5, seed=1)
    assert len(pairs) == 1 and {pairs[0][0]["body"], pairs[0][1]["body"]} == {a["body"], b["body"]}
    other_file = [v3.testing_candidate(raw(g, file=f"m/src/main/java/org/x{i}/Example.java"))
                  for i in range(3) for g in (GOLD1, GOLD2)]
    assert len(v3.pair_testing_candidates(other_file, project_cap=2, seed=1)) == 2


def test_refactoring_record_matches_ft_refactoring_prompt_and_parses():
    before = "class A {\n  void f() { int x = 1; use(x); }\n}\n"
    after = "class A {\n  void f() { int count = 1; use(count); }\n}\n"
    case = {"id": "marv-1", "source": "marv", "operation": "Rename Variable", "file_path": "p/A.java",
            "before": before, "class_name": "A", "target": {"method": "", "start": 2, "end": 2},
            "request": "Rename Variable x : int to count : int in method f()",
            "evaluation_level": "structural", "commit": "abc", "project": "o/p"}
    record = v3.refactoring_record(case, after)
    assert format_prompt(record) == render(case)  # the frozen ft_refactoring prompt
    assert ex.parse_answer(record["output"], case["file_path"]) == after
    assert record["refactoring_type"] == "Rename Variable" and record["format"] == v3.FORMAT


def test_finish_drops_over_length_instead_of_truncating_and_splits_by_project(tmp_path):
    records = [{"instruction": "i", "input": "x" * (10 if n % 2 else 500), "output": "{}",
                "project": f"p{n % 7}", "domain": "testing"} for n in range(40)]
    report = v3._finish(records, tmp_path, {"train": 100, "val": 100}, 3,
                        lambda r: len(r["input"]) < 100, {})
    assert report["dropped_over_token_limit"] == 20
    train = [json.loads(x) for x in (tmp_path / "train.jsonl").read_text().splitlines()]
    val = [json.loads(x) for x in (tmp_path / "val.jsonl").read_text().splitlines()]
    assert len(train) + len(val) == 20
    assert not {r["project"] for r in train} & {r["project"] for r in val}


def test_combined_is_row_balanced(tmp_path):
    for name, domain, n in (("t", "testing", 6), ("r", "refactoring", 4)):
        (tmp_path / name).mkdir()
        for split in ("train", "val"):
            rows = [json.dumps({"domain": domain, "i": i}) for i in range(n)]
            (tmp_path / name / f"{split}.jsonl").write_text("\n".join(rows) + "\n")
    stats = v3.build_combined_v3(tmp_path / "t", tmp_path / "r", tmp_path / "c")
    assert stats["train"]["domains"] == {"testing": 4, "refactoring": 4}


def test_build_testing_v3_end_to_end_from_archive(tmp_path):
    import io
    import tarfile
    archive = tmp_path / "train.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        n = 0
        for repo in range(4):
            for gold in (GOLD1, GOLD2, '@Test public void t() { assertThat(Example.twice(1)); }'):
                payload = json.dumps(raw(gold, repo_id=repo)).encode()
                info = tarfile.TarInfo(f"train/{repo}/{n}.json")
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
                n += 1
    report = v3.build_testing_v3(archive, tmp_path / "out", train_size=10, val_size=10, seed=0)
    assert report["candidates"] == 8 and report["pairs"] == 4
    assert report["rejections"] == {"assertion_library_not_in_jupiter_scaffold": 4}
    rows = [json.loads(x) for s in ("train", "val") for x in (tmp_path / "out" / f"{s}.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and all(parse_testing_bodies(r["output"]) for r in rows)


def test_refactoring_records_from_detector_contexts(tmp_path):
    before = "class A {\n  void f() { int x = 1; use(x); }\n}\n"
    after = "class A {\n  void f() { int count = 1; use(count); }\n}\n"
    loc = {"startLine": 2, "endLine": 2, "startColumn": 14, "endColumn": 24,
           "codeElementType": "VARIABLE_DECLARATION_STATEMENT", "filePath": "p/A.java"}
    event = {"type": "Rename Variable", "description": "Rename Variable x : int to count : int in method f()",
             "left": [{**loc, "codeElement": "x : int"}], "right": [{**loc, "codeElement": "count : int"}]}
    ok, bad = tmp_path / "contexts" / "ml4refactoring-1", tmp_path / "contexts" / "ml4refactoring-2"
    ok.mkdir(parents=True)
    bad.mkdir()
    (ok / "record-private.json").write_text(json.dumps({
        "id": "ml4refactoring-1", "source": "ml4refactoring", "refactoring_type": "Rename Variable",
        "file_path": "p/A.java", "input": before, "output": after, "project": "ant", "commit_sha": "c1"}))
    (ok / "events.json").write_text(json.dumps({"events": [event]}))
    (bad / "rejected.json").write_text("{}")
    records, reasons = v3.refactoring_records_from_contexts(tmp_path)
    assert reasons == {"rejected_or_undetected": 1} and len(records) == 1
    record = records[0]
    assert "Exact requested change: Rename Variable x : int to count : int" in record["instruction"]
    assert "Original target lines: 2..2" in record["instruction"]
    assert ex.parse_answer(record["output"], "p/A.java") == after
    assert record["project"] == "ant" and record["commit_sha"] == "c1"
