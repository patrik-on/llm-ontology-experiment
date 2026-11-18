from llm_ontology.benchmarks.junit_outcomes import test_outcomes as read_test_outcomes


def test_per_test_stability_detects_swapped_failure(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    template = '<testsuite><testcase classname="p.GeneratedBodyTests" name="testCase1">{}</testcase><testcase classname="p.GeneratedBodyTests" name="testCase2">{}</testcase></testsuite>'
    failure = '<failure type="org.opentest4j.AssertionFailedError"/>'
    (a / "TEST-jupiter.xml").write_text(template.format(failure, ""))
    (b / "TEST-jupiter.xml").write_text(template.format("", failure))
    assert read_test_outcomes(a) != read_test_outcomes(b)
    assert [r["status"] for r in read_test_outcomes(a)] == ["failure", "passed"]


def test_non_generated_classes_not_counted(tmp_path):
    (tmp_path / "TEST-jupiter.xml").write_text('<testsuite><testcase classname="p.ReferenceTests" name="gold"/></testsuite>')
    assert read_test_outcomes(tmp_path) == []


def test_missing_reports_are_not_passing_tests(tmp_path):
    assert read_test_outcomes(tmp_path) == []
