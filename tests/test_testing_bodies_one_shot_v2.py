import json


from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as demo, testing_bodies_v1 as v1
from llm_ontology.inference.structured_output import parse_testing_bodies
from llm_ontology.retrieval.query import build_retrieval_query


def test_demo_exact_body_contract_and_verbatim_assembly():
    answer = parse_testing_bodies(demo.DEMO_JSON)
    assert set(json.loads(demo.DEMO_JSON)) == {"testCase1", "testCase2"}
    source = demo.demo_source()
    assert source == v1.assemble(demo.DEMO_SCAFFOLD, answer)
    assert answer.testCase1 in source and answer.testCase2 in source
    assert "Labels.bracket" in answer.testCase1 and "assertEquals(" in answer.testCase1
    assert "Labels.bracket" in answer.testCase2 and "assertThrows(" in answer.testCase2
    assert "assertEquals(" not in demo.DEMO_SCAFFOLD
    assert "Lang" not in demo.DEMO_BLOCK and "Date" not in demo.DEMO_BLOCK


def test_only_demo_changes_prompt_and_not_retrieval_query():
    old = v1.apply_profile(demo.DEMO_CASE)
    new = demo.apply_profile(demo.DEMO_CASE)
    assert new.requirements == old.requirements
    assert new.input_text == old.input_text and new.project_context == old.project_context
    kwargs = dict(task="testing", input_text=old.input_text, requirements=old.requirements, approach="direct")
    before = v1.BodyPromptBuilder().build(instruction=old.instruction, **kwargs)
    after = demo.BodyPromptBuilder().build(instruction=new.instruction, **kwargs)
    assert after.text.count(demo.DEMO_BLOCK) == 1
    assert after.text.replace(demo.DEMO_BLOCK, "") == before.text
    assert after.prompt_template_version == demo.PROFILE
    def query(c):
        return build_retrieval_query(strategy="task_aware_v1", task="testing", input_text=c.input_text,
            requirements=c.requirements, structured_identity=c.structured_identity)
    assert query(new) == query(old) and demo.DEMO_BLOCK not in query(new)
