"""Typed loader for the handcrafted, never-indexable smoke dataset."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_ontology.benchmarks.contracts import BenchmarkCase
from llm_ontology.ingestion.identity import java_code_hash
from llm_ontology.ingestion.java import JavaParser
from llm_ontology.ingestion.manifest import DatasetManifest, UsageRole, read_dataset_manifest


BENCHMARK_NAME = "handcrafted_smoke_v1"
DEFAULT_ROOT = Path("data/smoke")
CASE_FILES = (Path("testing/cases.jsonl"), Path("refactoring/cases.jsonl"))


class SmokeDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    TRICKY = "tricky"


class ValidationRuleName(StrEnum):
    CODE_COMPILES = "code_compiles"
    GENERATED_TESTS_PASS = "generated_tests_pass"
    INVOKES_FOCAL_METHOD = "invokes_focal_method"
    MINIMUM_TEST_METHODS = "minimum_test_methods"
    REQUIRED_SCENARIOS = "required_scenarios"
    EXPECTED_EXCEPTION_ASSERTED = "expected_exception_asserted"
    PUBLIC_API_PRESERVED = "public_api_preserved"
    BEHAVIOR_TESTS_PASS = "behavior_tests_pass"
    HELPER_METHOD_EXISTS = "helper_method_exists"
    FOCAL_METHOD_SHORTER = "focal_method_shorter"
    DEAD_CODE_REMOVED = "dead_code_removed"
    BOOLEAN_SIMPLIFIED = "boolean_expression_simplified"
    IDENTIFIER_RENAMED = "identifier_renamed"
    DUPLICATION_REDUCED = "duplication_reduced"


class ValidationRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: ValidationRuleName
    value: str | int | bool | list[str] | None = None


class TestingSmokeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["testing"] = "testing"
    class_name: str
    source_code: str
    focal_method: str
    test_framework: Literal["JUnit 5"] = "JUnit 5"
    package_name: str = ""
    imports: list[str] = Field(default_factory=list)
    requirements: str = ""
    fixture_path: str


class RefactoringSmokeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["refactoring"] = "refactoring"
    class_name: str
    source_code: str
    focal_method: str
    requirements: str
    fixture_path: str
    behavior_test_path: str


class TestingExpectedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["testing"] = "testing"
    must_compile: bool = True
    must_use_framework: Literal["JUnit 5"] = "JUnit 5"
    must_call_method: str
    minimum_test_methods: int = Field(ge=1)
    required_scenarios: list[str] = Field(min_length=1)
    expected_exception_types: list[str] = Field(default_factory=list)


class RefactoringExpectedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["refactoring"] = "refactoring"
    expected_refactoring_types: list[str] = Field(min_length=1)
    must_compile: bool = True
    must_preserve_behavior: bool = True
    must_preserve_public_api: bool = True
    structural_expectations: list[str] = Field(default_factory=list)
    reference_code: str | None = None


SmokeInput = Annotated[TestingSmokeInput | RefactoringSmokeInput, Field(discriminator="kind")]
SmokeExpectedOutput = Annotated[
    TestingExpectedOutput | RefactoringExpectedOutput,
    Field(discriminator="kind"),
]


class SmokeCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^(testing|refactoring)_(easy|medium|tricky)_\d{3}$")
    task: Literal["testing", "refactoring"]
    difficulty: SmokeDifficulty
    title: str = Field(min_length=3)
    input: SmokeInput
    expected_process: list[str] = Field(min_length=1)
    expected_output: SmokeExpectedOutput
    validation_rules: list[ValidationRule] = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    notes: str = ""
    input_code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_input_code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    focal_method_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def task_specific_models_match(self) -> SmokeCase:
        if self.input.kind != self.task or self.expected_output.kind != self.task:
            raise ValueError("task, input.kind and expected_output.kind must match")
        if self.expected_output.must_compile is not True:
            raise ValueError("Every smoke reference output must require compilation.")
        return self

    def to_benchmark_case(self) -> BenchmarkCase:
        if self.task == "testing":
            instruction = (
                "Generate one complete, compilable JUnit 5 test class for the supplied "
                "Java class and focal method. Return only Java source code."
            )
        else:
            instruction = (
                "Refactor the supplied Java code while preserving observable behavior and "
                "public method signatures. Return only the complete refactored Java source."
            )
        if self.input.requirements:
            instruction += f" Requirements: {self.input.requirements}"
        reference_output = (
            self.expected_output.reference_code or ""
            if isinstance(self.expected_output, RefactoringExpectedOutput)
            else ""
        )
        return BenchmarkCase(
            case_id=self.id,
            benchmark=BENCHMARK_NAME,
            task=self.task,
            instruction=instruction,
            input_text=self.input.source_code,
            reference_output=reference_output,
            metadata={
                "difficulty": self.difficulty.value,
                "title": self.title,
                "class_name": self.input.class_name,
                "focal_method": self.input.focal_method,
                "usage_role": UsageRole.SMOKE_EVALUATION.value,
                "allowed_for_indexing": False,
            },
        )


class SmokeHashes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_code_hash: str
    normalized_input_code_hash: str
    focal_method_hash: str


def compute_smoke_hashes(input_data: TestingSmokeInput | RefactoringSmokeInput) -> SmokeHashes:
    parser_result = JavaParser().parse(input_data.source_code)
    matches = [
        method for method in parser_result.methods if method.method_name == input_data.focal_method
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one focal method {input_data.focal_method!r} in "
            f"{input_data.class_name}, found {len(matches)}."
        )
    return SmokeHashes(
        input_code_hash=hashlib.sha256(input_data.source_code.encode("utf-8")).hexdigest(),
        normalized_input_code_hash=java_code_hash(input_data.source_code),
        focal_method_hash=java_code_hash(matches[0].content),
    )


def load_smoke_cases(
    root: str | Path = DEFAULT_ROOT,
    *,
    verify_hashes: bool = True,
) -> list[SmokeCase]:
    dataset_root = Path(root)
    cases: list[SmokeCase] = []
    for relative_path in CASE_FILES:
        path = dataset_root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Smoke case file does not exist: {path}")
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    case = SmokeCase.model_validate(json.loads(line))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"Invalid smoke case at {path}:{line_number}: {exc}") from exc
                if verify_hashes:
                    actual = compute_smoke_hashes(case.input)
                    stored = SmokeHashes(
                        input_code_hash=case.input_code_hash,
                        normalized_input_code_hash=case.normalized_input_code_hash,
                        focal_method_hash=case.focal_method_hash,
                    )
                    if actual != stored:
                        raise ValueError(f"Stored hashes are stale for smoke case {case.id}.")
                cases.append(case)
    _validate_dataset_invariants(cases)
    return cases


def load_smoke_benchmark(root: str | Path = DEFAULT_ROOT) -> list[BenchmarkCase]:
    return [case.to_benchmark_case() for case in load_smoke_cases(root)]


def load_smoke_manifest(root: str | Path = DEFAULT_ROOT) -> DatasetManifest:
    dataset_root = Path(root).resolve()
    manifest = read_dataset_manifest(dataset_root / "manifest.yaml")
    if manifest.dataset_name != BENCHMARK_NAME or manifest.dataset_version != "1.0":
        raise ValueError("Unexpected smoke dataset identity or version.")
    if manifest.usage_role != UsageRole.SMOKE_EVALUATION:
        raise ValueError("Smoke manifest must use usage_role=smoke_evaluation.")
    if manifest.allowed_for_indexing:
        raise ValueError("Smoke manifest must forbid indexing.")
    if (
        manifest.sample_count != 24
        or manifest.case_count != 24
        or manifest.tasks != ["testing", "refactoring"]
    ):
        raise ValueError("Smoke manifest must declare 24 testing/refactoring cases.")
    manifest.require_source_matches(root=dataset_root.parents[1])
    return manifest


def _validate_dataset_invariants(cases: list[SmokeCase]) -> None:
    ids = [case.id for case in cases]
    hashes = [case.normalized_input_code_hash for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Smoke case IDs must be unique.")
    if len(hashes) != len(set(hashes)):
        raise ValueError("Smoke normalized input hashes must be unique.")
    if len(cases) != 24:
        raise ValueError(f"Smoke dataset must contain exactly 24 cases, found {len(cases)}.")
    distribution = Counter((case.task, case.difficulty.value) for case in cases)
    expected = {
        (task, difficulty): 4
        for task in ("testing", "refactoring")
        for difficulty in ("easy", "medium", "tricky")
    }
    if distribution != expected:
        raise ValueError(f"Unexpected smoke task/difficulty distribution: {distribution}.")
    for case in cases:
        expected_prefix = f"{case.task}_{case.difficulty.value}_"
        if not case.id.startswith(expected_prefix):
            raise ValueError(f"Smoke case ID does not match its task/difficulty: {case.id}.")
