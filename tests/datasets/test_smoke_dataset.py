from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from llm_ontology.benchmarks.registry import available_benchmarks, load_benchmark
from llm_ontology.benchmarks.smoke import (
    BENCHMARK_NAME,
    RefactoringExpectedOutput,
    TestingExpectedOutput as SmokeTestingExpectedOutput,
    compute_smoke_hashes,
    load_smoke_cases,
    load_smoke_manifest,
)
from llm_ontology.benchmarks.smoke_validation import (
    audit_smoke_leakage,
    discover_java_toolchain,
    discover_junit_classpath,
    validate_smoke_dataset,
)
from llm_ontology.ingestion.manifest import UsageRole


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SMOKE_ROOT = PROJECT_ROOT / "data/smoke"


def test_smoke_dataset_has_exact_balanced_contract() -> None:
    cases = load_smoke_cases(SMOKE_ROOT)

    assert len(cases) == 24
    assert Counter(case.task for case in cases) == {"testing": 12, "refactoring": 12}
    assert Counter((case.task, case.difficulty.value) for case in cases) == {
        (task, difficulty): 4
        for task in ("testing", "refactoring")
        for difficulty in ("easy", "medium", "tricky")
    }
    expected_ids = {
        f"{task}_{difficulty}_{number:03d}"
        for task in ("testing", "refactoring")
        for difficulty in ("easy", "medium", "tricky")
        for number in range(1, 5)
    }
    assert {case.id for case in cases} == expected_ids
    assert len({case.id for case in cases}) == 24


def test_smoke_sources_fixtures_and_hashes_are_consistent() -> None:
    cases = load_smoke_cases(SMOKE_ROOT)
    normalized_hashes = set()
    focal_hashes = set()

    for case in cases:
        assert case.input.source_code.strip()
        fixture = PROJECT_ROOT / case.input.fixture_path
        assert fixture.read_text(encoding="utf-8").strip() == case.input.source_code.strip()
        actual = compute_smoke_hashes(case.input)
        assert case.input_code_hash == actual.input_code_hash
        assert case.input_code_hash == hashlib.sha256(
            case.input.source_code.encode("utf-8")
        ).hexdigest()
        assert case.normalized_input_code_hash == actual.normalized_input_code_hash
        assert case.focal_method_hash == actual.focal_method_hash
        assert case.input_code_hash != "0" * 64
        normalized_hashes.add(case.normalized_input_code_hash)
        focal_hashes.add(case.focal_method_hash)

    assert len(normalized_hashes) == 24
    assert len(focal_hashes) == 24


def test_expected_outputs_match_validation_rules() -> None:
    for case in load_smoke_cases(SMOKE_ROOT):
        rules = {rule.rule.value: rule.value for rule in case.validation_rules}
        assert "code_compiles" in rules
        assert case.expected_output.must_compile is True

        if isinstance(case.expected_output, SmokeTestingExpectedOutput):
            expected = case.expected_output
            assert expected.must_use_framework == "JUnit 5"
            assert rules["invokes_focal_method"] == expected.must_call_method
            assert rules["minimum_test_methods"] == expected.minimum_test_methods
            scenario_categories = rules["required_scenarios"]
            assert isinstance(scenario_categories, list)
            assert scenario_categories
            assert "generated_tests_pass" in rules
            if expected.expected_exception_types:
                asserted = rules["expected_exception_asserted"]
                asserted_types = [asserted] if isinstance(asserted, str) else asserted
                assert asserted_types == expected.expected_exception_types
        else:
            assert isinstance(case.expected_output, RefactoringExpectedOutput)
            assert case.expected_output.must_preserve_behavior is True
            assert case.expected_output.must_preserve_public_api is True
            assert case.expected_output.reference_code
            assert "behavior_tests_pass" in rules
            assert "public_api_preserved" in rules
            behavior_path = PROJECT_ROOT / case.input.behavior_test_path
            assert behavior_path.is_file()


def test_manifest_and_benchmark_adapter_forbid_indexing_and_hide_evaluator_data() -> None:
    manifest = load_smoke_manifest(SMOKE_ROOT)

    assert manifest.dataset_name == BENCHMARK_NAME
    assert manifest.dataset_version == "1.0"
    assert manifest.usage_role == UsageRole.SMOKE_EVALUATION
    assert manifest.allowed_for_indexing is False
    assert manifest.sample_count == manifest.case_count == 24
    assert manifest.metadata["never_for_training"] is True
    assert manifest.metadata["never_for_retrieval"] is True
    with pytest.raises(ValueError, match="forbids indexing"):
        manifest.require_indexable()

    assert BENCHMARK_NAME in available_benchmarks()
    source_cases = load_smoke_cases(SMOKE_ROOT)
    benchmark_cases = load_benchmark("smoke", root=SMOKE_ROOT)
    assert len(benchmark_cases) == 24
    for source, adapted in zip(source_cases, benchmark_cases, strict=True):
        assert adapted.benchmark == BENCHMARK_NAME
        assert adapted.metadata["usage_role"] == "smoke_evaluation"
        assert adapted.metadata["allowed_for_indexing"] is False
        assert adapted.input_text == source.input.source_code
        assert all(step not in adapted.instruction for step in source.expected_process)
        assert "BehaviorTest" not in adapted.input_text
        if source.task == "testing":
            assert adapted.reference_output == ""


def test_checked_in_leakage_report_is_safe_and_matches_current_fingerprints() -> None:
    report_path = SMOKE_ROOT / "leakage_report.json"
    stored = json.loads(report_path.read_text(encoding="utf-8"))
    assert stored["overall_safe"] is True
    assert stored["allowed_for_indexing"] is False
    assert set(stored["collections"]) == {"mixed", "testing_db", "refactoring_db"}
    assert all(item["overlap_count"] == 0 for item in stored["collections"].values())

    required_local_artifacts = (
        PROJECT_ROOT / "artifacts/split_audits/testing_retrieval_fingerprints.jsonl",
        PROJECT_ROOT / "artifacts/split_audits/refactoring_retrieval_fingerprints.jsonl",
        PROJECT_ROOT / "data/chroma/ollama_bge_m3/manifests/mixed.json",
    )
    if not all(path.is_file() for path in required_local_artifacts):
        pytest.skip("Current production fingerprint artifacts are not present in this clone.")
    current = audit_smoke_leakage(SMOKE_ROOT, project_root=PROJECT_ROOT)
    assert current["overall_safe"] is True
    assert all(item["overlap_count"] == 0 for item in current["collections"].values())
    assert current["smoke_manifest_id"] == stored["smoke_manifest_id"]


def test_all_java_inputs_and_refactoring_behavior_fixtures() -> None:
    if discover_java_toolchain() is None or not discover_junit_classpath():
        pytest.skip("JDK/JUnit integration dependencies are not installed.")

    summary = validate_smoke_dataset(SMOKE_ROOT)

    assert summary.compiled_inputs == 24
    assert summary.compiled_references == 12
    assert summary.behavior_cases_passed == 12
    assert summary.behavior_executions == 24
