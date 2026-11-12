import json

import pytest

from llm_ontology.benchmarks import defects4j_bodies_pilot as pilot
from llm_ontology.benchmarks.defects4j_bodies_one_shot import verify_request
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


def test_three_arm_exclusive_cap_and_no_multi(tmp_path, monkeypatch):
    plan = json.loads(pilot.ONE_SHOT_CONFIG.read_text())
    (tmp_path / "job_plan.json").write_text(json.dumps(plan))
    (tmp_path / "frozen-prompts").mkdir()
    monkeypatch.setattr(pilot, "usable", lambda root: True)
    for arm in plan["arms"]:
        out = tmp_path / "predictions" / arm
        out.mkdir(parents=True)
        (tmp_path / "frozen-prompts" / (arm + ".txt")).write_text("prompt" + demo.DEMO_BLOCK)
        ledger = pilot.Ledger(tmp_path, arm)
        ledger.charge({"prompt": "prompt" + demo.DEMO_BLOCK})
        with pytest.raises(FileExistsError):
            ledger.charge({"prompt": "prompt" + demo.DEMO_BLOCK})
        with pytest.raises(ValueError):
            verify_request(tmp_path, arm, {"prompt": "changed evidence" + demo.DEMO_BLOCK})
    with pytest.raises(ValueError):
        pilot.Ledger(tmp_path, "rag_multi")
    assert len(list(tmp_path.glob("predictions/*/dispatch.json"))) == 3
    assert all(json.loads(p.read_text())["maximum"] == 3 for p in tmp_path.glob("predictions/*/dispatch.json"))


def test_historical_default_unchanged():
    assert json.loads(pilot.CONFIG.read_text())["max_actual_generation_calls"] == 4
    assert pilot.profile_module(v1.PROFILE) is v1
    assert pilot.profile_module(demo.PROFILE) is demo
    from llm_ontology.benchmarks.defects4j_runner import body_options
    assert type(body_options(True)["prompt_builder"]) is v1.BodyPromptBuilder
    assert type(body_options(True, profile=demo.PROFILE)["prompt_builder"]) is demo.BodyPromptBuilder
    assert body_options(False, profile=demo.PROFILE) == {}
