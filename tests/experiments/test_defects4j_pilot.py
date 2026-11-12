from pathlib import Path

import pytest

from llm_ontology.benchmarks.defects4j import load_config
from llm_ontology.benchmarks.defects4j_pilot import DEFAULT_CONFIG, attempt, load_protocol, summarize


def test_profile_optin_preserves_frozen_default():
    old = load_config(Path("configs/benchmarks/defects4j_jupiter_v1.yaml"))
    raw, configs = load_protocol(DEFAULT_CONFIG)
    assert old.prompt_profile is None and old.max_new_tokens == 2048
    assert [c.case_id for c in configs] == ["Lang-24", "Lang-26", "Lang-27"]
    assert all(c.max_new_tokens == 4096 and c.random_seed == 42 for c in configs)
    assert all(c.prompt_profile == "testing-full-class-v2" and c.repeats == 2 for c in configs)
    assert raw["max_generation_calls"] == 9


def test_exclusive_attempts_and_failed_attempt_denominator(tmp_path):
    _, configs = load_protocol(DEFAULT_CONFIG)
    out = attempt(tmp_path, configs[0], "ft_testing")
    (out / "failure.json").write_text('{"status":"generation_failure"}')
    with pytest.raises(FileExistsError):
        attempt(tmp_path, configs[0], "ft_testing")
    report = summarize(tmp_path, configs)
    assert report["denominator"] == 9 and report["per_arm_denominator"] == 3
    assert report["overall"]["attempted"] == 1
    assert report["overall"]["generated"] == 0
    assert report["overall"]["genuine_bug_detection"] == 0


def test_invalid_config_rejects_duplicate_cases(tmp_path):
    import yaml
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text())
    raw["cases"][2] = raw["cases"][0]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="distinct"):
        load_protocol(path)


def test_test_count_is_adherence_not_functional_gate(tmp_path):
    import json
    _, configs = load_protocol(DEFAULT_CONFIG)
    out = attempt(tmp_path, configs[0], "ft_testing")
    (out / "generation.json").write_text(json.dumps({"generation": {"finish_reason": "eos", "output_truncated": False}}))
    metrics = out.parent.parent / "metrics" / "ft_testing"
    metrics.mkdir(parents=True)
    run = {"status": "passed", "compile": {"status": "completed", "returncode": 0},
           "console_summary": {"tests_started": 5, "tests_successful": 5}}
    (metrics / "evaluation.json").write_text(json.dumps({"fixed_pass": True, "detected_bug": False,
        "outcomes": {"fixed": [run, run], "buggy": [run, run]}}))
    row = summarize(tmp_path, configs)["cells"][0]
    assert row["fixed_class_pass"] and row["compiled"]
    assert not row["test_count_adherence_only"]
    assert len(row["revisions"]["fixed"]) == 2
