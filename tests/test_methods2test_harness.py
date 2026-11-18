"Verbatim harness/prompt regression tests for the current matrix."

from llm_ontology.benchmarks.methods2test_harness import package_from_path, wrap_record

from llm_ontology.benchmarks.matrix_support import ft_case

from llm_ontology.inference.experiment_runner import ExperimentCase

from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile


def test_verbatim_source_and_private_reference():
    raw = {
        "focal_class": {
            "file": "p/src/main/java/a/b/Util.java",
            "identifier": "Util",
            "fields": [{"var_name": "X", "original_string": "static int X=2;"}],
        },
        "focal_method": {"body": "public static int twice(int x) { return x * X; }"},
        "test_case": {"body": "@Test void t(){ assertEquals(4,Util.twice(2)); }"},
    }
    production, gold, policy = wrap_record(
        {"raw": raw}, {"imports": [], "fields": ["X"], "assertions": "jupiter"}
    )
    assert raw["focal_method"]["body"] in production
    assert raw["test_case"]["body"] in gold
    assert raw["test_case"]["body"] not in production
    assert policy["method_logic"] == "verbatim"
    assert package_from_path(raw["focal_class"]["file"]) == "a.b"


def test_shared_one_shot_ft_content():
    case = ExperimentCase(
        case_id="fixture",
        instruction="not gold",
        input_text="package a.b;\npublic class Util {}",
        structured_identity={"class_name": "a.b.Util"},
    )
    applied = profile.apply_profile(case)
    instruction = ft_case(applied).instruction
    assert instruction.count(profile.DEMO_BLOCK) == 1
    assert "testCase1" in instruction and "testCase2" in instruction
    assert applied.input_text == case.input_text
