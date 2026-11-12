import json
from pathlib import Path

import pytest

from llm_ontology.benchmarks.methods2test import package_from_path, wrap_record
from llm_ontology.benchmarks.methods2test_pilot import ARMS, Ledger, ft_case
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile


def test_verbatim_source_and_private_reference():
    raw = {"focal_class": {"file": "p/src/main/java/a/b/Util.java", "identifier": "Util",
                           "fields": [{"var_name": "X", "original_string": "static int X=2;"}]},
           "focal_method": {"body": "public static int twice(int x) { return x * X; }"},
           "test_case": {"body": "@Test void t(){ assertEquals(4,Util.twice(2)); }"}}
    production, gold, policy = wrap_record({"raw": raw}, {"imports": [], "fields": ["X"], "assertions": "jupiter"})
    assert raw["focal_method"]["body"] in production
    assert raw["test_case"]["body"] in gold
    assert raw["test_case"]["body"] not in production
    assert policy["method_logic"] == "verbatim"
    assert package_from_path(raw["focal_class"]["file"]) == "a.b"


def test_all_twenty_cells_exclusive(tmp_path):
    ids = [str(i) for i in range(5)]
    (tmp_path / "selection.json").write_text(json.dumps({"ids": ids}))
    for ident in ids:
        for arm in ARMS:
            out = tmp_path / "cases" / ident / "predictions" / arm
            out.mkdir(parents=True)
            ledger = Ledger(tmp_path, ident, arm)
            ledger.charge({"prompt": "same"})
            with pytest.raises(FileExistsError):
                ledger.charge({"prompt": "retry forbidden"})
    assert len(list(tmp_path.glob("cases/*/predictions/*/dispatch.json"))) == 20
    with pytest.raises(ValueError):
        Ledger(tmp_path, "unplanned", ARMS[0])


def test_shared_one_shot_ft_content():
    case = ExperimentCase(case_id="fixture", instruction="not gold", input_text="package a.b;\npublic class Util {}",
                          structured_identity={"class_name": "a.b.Util"})
    applied = profile.apply_profile(case)
    instruction = ft_case(applied).instruction
    assert instruction.count(profile.DEMO_BLOCK) == 1
    assert "testCase1" in instruction and "testCase2" in instruction
    assert applied.input_text == case.input_text


def test_protocol_finite_nonindexable():
    p = json.loads(Path("configs/benchmarks/methods2test_eval_five_v1.json").read_text())
    assert p["max_actual_generation_calls"] == len(ARMS) * p["cases"] == 20
    assert p["usage_role"] == "validation" and p["official_split"] == "eval"
    assert not p["indexing_allowed"]
    assert p["retries"] == p["repairs"] == 0
