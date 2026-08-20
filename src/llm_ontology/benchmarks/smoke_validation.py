"""Validation and leakage auditing for the handcrafted smoke benchmark."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from llm_ontology.benchmarks.smoke import (
    BENCHMARK_NAME,
    CASE_FILES,
    DEFAULT_ROOT,
    RefactoringExpectedOutput,
    RefactoringSmokeInput,
    SmokeCase,
    TestingExpectedOutput,
    compute_smoke_hashes,
    load_smoke_cases,
    load_smoke_manifest,
)
from llm_ontology.ingestion.identity import (
    CaseIdentity,
    SampleFingerprint,
    detect_leakage,
    read_fingerprints,
)
from llm_ontology.retrieval.models import normalize_content, sha256_text


JUNIT_ARTIFACTS = (
    ("org/junit/jupiter", "junit-jupiter-api"),
    ("org/junit/jupiter", "junit-jupiter-engine"),
    ("org/junit/platform", "junit-platform-commons"),
    ("org/junit/platform", "junit-platform-engine"),
    ("org/junit/platform", "junit-platform-launcher"),
    ("org/opentest4j", "opentest4j"),
    ("org/apiguardian", "apiguardian-api"),
)


@dataclass(frozen=True)
class JavaToolchain:
    javac: str
    java: str
    windows_paths_from_wsl: bool = False

    @property
    def description(self) -> str:
        return f"javac={self.javac}; java={self.java}"


@dataclass(frozen=True)
class SmokeValidationSummary:
    cases: int
    fixtures_checked: int
    compiled_inputs: int
    compiled_references: int
    behavior_cases_passed: int
    behavior_executions: int
    java_toolchain: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "fixtures_checked": self.fixtures_checked,
            "compiled_inputs": self.compiled_inputs,
            "compiled_references": self.compiled_references,
            "behavior_cases_passed": self.behavior_cases_passed,
            "behavior_executions": self.behavior_executions,
            "java_toolchain": self.java_toolchain,
        }


def refresh_smoke_hashes(root: str | Path = DEFAULT_ROOT) -> None:
    """Recompute generated hash fields while retaining JSONL record ordering."""

    dataset_root = Path(root)
    for relative_path in CASE_FILES:
        path = dataset_root / relative_path
        records: list[str] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    case = SmokeCase.model_validate(json.loads(line))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"Invalid smoke case at {path}:{line_number}: {exc}") from exc
                hashes = compute_smoke_hashes(case.input)
                updated = case.model_copy(update=hashes.model_dump())
                records.append(json.dumps(updated.model_dump(mode="json"), separators=(",", ":")))
        path.write_text("\n".join(records) + "\n", encoding="utf-8")


def validate_smoke_dataset(
    root: str | Path = DEFAULT_ROOT,
    *,
    require_java: bool = True,
) -> SmokeValidationSummary:
    dataset_root = Path(root).resolve()
    cases = load_smoke_cases(dataset_root)
    load_smoke_manifest(dataset_root)
    fixtures_checked = _validate_metadata_and_fixtures(cases, dataset_root)

    toolchain = discover_java_toolchain()
    junit_jars = discover_junit_classpath()
    if toolchain is None or not junit_jars:
        missing = []
        if toolchain is None:
            missing.append("JDK (javac/java)")
        if not junit_jars:
            missing.append("JUnit 5 Maven artifacts")
        message = "Cannot perform Java smoke validation; missing " + " and ".join(missing)
        if require_java:
            raise RuntimeError(message)
        return SmokeValidationSummary(
            cases=len(cases),
            fixtures_checked=fixtures_checked,
            compiled_inputs=0,
            compiled_references=0,
            behavior_cases_passed=0,
            behavior_executions=0,
            java_toolchain="not available",
        )

    compiled_inputs = 0
    compiled_references = 0
    behavior_cases_passed = 0
    behavior_executions = 0
    harness = dataset_root / "harness" / "SmokeTestLauncher.java"
    if not harness.is_file():
        raise FileNotFoundError(f"Missing shared smoke harness: {harness}")

    temporary_root = dataset_root.parents[1] / "artifacts" / "smoke_validation"
    temporary_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="run-", dir=temporary_root) as temp_name:
            temp = Path(temp_name)
            for case in cases:
                fixture = _repository_path(dataset_root, case.input.fixture_path)
                input_out = temp / case.id / "input"
                sources = [fixture]
                run_behavior = isinstance(case.input, RefactoringSmokeInput)
                if run_behavior:
                    sources.extend(
                        [
                            _repository_path(dataset_root, case.input.behavior_test_path),
                            harness,
                        ]
                    )
                _compile_java(toolchain, sources, input_out, junit_jars if run_behavior else ())
                compiled_inputs += 1
                if run_behavior:
                    _run_behavior_test(toolchain, input_out, junit_jars)
                    behavior_executions += 1

                    expected = case.expected_output
                    if not isinstance(expected, RefactoringExpectedOutput):
                        raise TypeError(f"Refactoring case has wrong expected output: {case.id}")
                    if not expected.reference_code:
                        raise ValueError(f"No reference code is available for {case.id}.")
                    reference_dir = temp / case.id / "reference-source"
                    reference_dir.mkdir(parents=True, exist_ok=True)
                    reference_source = reference_dir / "Input.java"
                    reference_source.write_text(expected.reference_code + "\n", encoding="utf-8")
                    reference_out = temp / case.id / "reference"
                    _compile_java(
                        toolchain,
                        [reference_source, sources[1], harness],
                        reference_out,
                        junit_jars,
                    )
                    _run_behavior_test(toolchain, reference_out, junit_jars)
                    compiled_references += 1
                    behavior_executions += 1
                    behavior_cases_passed += 1
    finally:
        try:
            temporary_root.rmdir()
        except OSError:
            pass

    return SmokeValidationSummary(
        cases=len(cases),
        fixtures_checked=fixtures_checked,
        compiled_inputs=compiled_inputs,
        compiled_references=compiled_references,
        behavior_cases_passed=behavior_cases_passed,
        behavior_executions=behavior_executions,
        java_toolchain=toolchain.description,
    )


def audit_smoke_leakage(
    root: str | Path = DEFAULT_ROOT,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    dataset_root = Path(root).resolve()
    repository_root = Path(project_root).resolve() if project_root else dataset_root.parents[1]
    cases = load_smoke_cases(dataset_root)
    manifest = load_smoke_manifest(dataset_root)
    benchmark_by_task = {
        task: [_smoke_fingerprint(case) for case in cases if case.task == task]
        for task in ("testing", "refactoring")
    }
    fingerprint_paths = {
        "testing": repository_root
        / "artifacts/split_audits/testing_retrieval_fingerprints.jsonl",
        "refactoring": repository_root
        / "artifacts/split_audits/refactoring_retrieval_fingerprints.jsonl",
    }
    retrieval = {
        task: read_fingerprints(path) for task, path in fingerprint_paths.items()
    }

    collection_tasks = {
        "testing_db": ("testing",),
        "refactoring_db": ("refactoring",),
        "mixed": ("testing", "refactoring"),
    }
    collections: dict[str, Any] = {}
    for collection, tasks in collection_tasks.items():
        collection_manifest_path = (
            repository_root
            / "data/chroma/ollama_bge_m3/manifests"
            / f"{collection}.json"
        )
        collection_manifest = json.loads(collection_manifest_path.read_text(encoding="utf-8"))
        indexed = [item for task in tasks for item in retrieval[task]]
        benchmark = [item for task in tasks for item in benchmark_by_task[task]]
        report = detect_leakage(
            indexed,
            benchmark,
            indexed_manifest_id="+".join(collection_manifest["dataset_manifests"]),
            benchmark_manifest_id=manifest.manifest_id,
        )
        collections[collection] = {
            "document_count": collection_manifest["document_count"],
            "retrieval_fingerprint_records": len(indexed),
            "smoke_cases_compared": len(benchmark),
            "tasks": list(tasks),
            "dataset_manifest_ids": collection_manifest["dataset_manifests"],
            "overlap_count": len(report.overlaps),
            "safe": report.safe,
            "overlaps": [overlap.model_dump(mode="json") for overlap in report.overlaps],
        }

    return {
        "dataset_name": BENCHMARK_NAME,
        "dataset_version": manifest.dataset_version,
        "smoke_manifest_id": manifest.manifest_id,
        "usage_role": manifest.usage_role.value,
        "allowed_for_indexing": manifest.allowed_for_indexing,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "comparison_fields": [
            "normalized input code",
            "focal method code",
            "normalized full document",
            "structured identity when available",
        ],
        "fingerprint_sources": {
            task: {
                "path": path.relative_to(repository_root).as_posix(),
                "records": len(retrieval[task]),
            }
            for task, path in fingerprint_paths.items()
        },
        "collections": collections,
        "overall_safe": all(item["safe"] for item in collections.values()),
    }


def discover_java_toolchain() -> JavaToolchain | None:
    javac_override = os.environ.get("SMOKE_JAVAC")
    java_override = os.environ.get("SMOKE_JAVA")
    if javac_override and java_override:
        return JavaToolchain(javac_override, java_override)

    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac and java:
        return JavaToolchain(javac, java)

    if _is_wsl() and shutil.which("cmd.exe") and shutil.which("wslpath"):
        windows_javac = _where_windows_executable("javac.exe")
        windows_java = _where_windows_executable("java.exe")
        if windows_javac and windows_java:
            return JavaToolchain(windows_javac, windows_java, windows_paths_from_wsl=True)
    return None


def discover_junit_classpath() -> tuple[Path, ...]:
    override = os.environ.get("SMOKE_JUNIT_CLASSPATH")
    if override:
        return tuple(Path(item) for item in override.split(os.pathsep) if item)

    for repository in _candidate_maven_repositories():
        jars = []
        for group, artifact in JUNIT_ARTIFACTS:
            artifact_root = repository / group / artifact
            candidates = sorted(
                (
                    jar
                    for jar in artifact_root.glob(f"*/{artifact}-*.jar")
                    if not jar.name.endswith(("-sources.jar", "-javadoc.jar"))
                ),
                reverse=True,
            )
            if not candidates:
                jars = []
                break
            jars.append(candidates[0])
        if jars:
            return tuple(jars)
    return ()


def _candidate_maven_repositories() -> Iterable[Path]:
    yielded: set[Path] = set()
    native = Path.home() / ".m2/repository"
    if native.is_dir():
        yielded.add(native)
        yield native
    if _is_wsl() and shutil.which("cmd.exe") and shutil.which("wslpath"):
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "echo", "%USERPROFILE%"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            profile = _wsl_path(result.stdout.strip())
            repository = Path(profile) / ".m2/repository"
            if repository.is_dir() and repository not in yielded:
                yield repository


def _validate_metadata_and_fixtures(cases: list[SmokeCase], dataset_root: Path) -> int:
    fixtures_checked = 0
    for case in cases:
        fixture = _repository_path(dataset_root, case.input.fixture_path)
        if not fixture.is_file():
            raise FileNotFoundError(f"Missing input fixture for {case.id}: {fixture}")
        if fixture.read_text(encoding="utf-8").strip() != case.input.source_code.strip():
            raise ValueError(f"Input fixture differs from source_code for {case.id}.")
        fixtures_checked += 1

        rules = {rule.rule.value for rule in case.validation_rules}
        if "code_compiles" not in rules:
            raise ValueError(f"Missing code_compiles rule for {case.id}.")
        if isinstance(case.expected_output, TestingExpectedOutput):
            required = {
                "generated_tests_pass",
                "invokes_focal_method",
                "minimum_test_methods",
                "required_scenarios",
            }
            if not required.issubset(rules):
                raise ValueError(f"Incomplete testing validation rules for {case.id}.")
            if case.expected_output.must_call_method != case.input.focal_method:
                raise ValueError(f"Expected method does not match focal method for {case.id}.")
        else:
            required = {"behavior_tests_pass", "public_api_preserved"}
            if not required.issubset(rules):
                raise ValueError(f"Incomplete refactoring validation rules for {case.id}.")
            if not isinstance(case.input, RefactoringSmokeInput):
                raise TypeError(f"Refactoring case has wrong input model: {case.id}")
            behavior = _repository_path(dataset_root, case.input.behavior_test_path)
            if not behavior.is_file():
                raise FileNotFoundError(f"Missing behavior fixture for {case.id}: {behavior}")
            fixtures_checked += 1
    return fixtures_checked


def _smoke_fingerprint(case: SmokeCase) -> SampleFingerprint:
    return SampleFingerprint(
        identity=CaseIdentity(
            dataset=BENCHMARK_NAME,
            case_id=case.id,
            class_name=case.input.class_name,
            method_name=case.input.focal_method,
        ),
        input_code_hash=case.normalized_input_code_hash,
        focal_method_hash=case.focal_method_hash,
        full_document_hash=sha256_text(normalize_content(case.input.source_code)),
        metadata={"task": case.task, "difficulty": case.difficulty.value},
    )


def _compile_java(
    toolchain: JavaToolchain,
    sources: list[Path],
    output: Path,
    classpath: tuple[Path, ...],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    command = [toolchain.javac, "-encoding", "UTF-8", "-d", _java_path(toolchain, output)]
    if classpath:
        command.extend(["-cp", _classpath(toolchain, classpath)])
    command.extend(_java_path(toolchain, source) for source in sources)
    _run_checked(command, "Java compilation")


def _run_behavior_test(
    toolchain: JavaToolchain,
    output: Path,
    junit_jars: tuple[Path, ...],
) -> None:
    classpath = (output, *junit_jars)
    command = [
        toolchain.java,
        "-cp",
        _classpath(toolchain, classpath),
        "SmokeTestLauncher",
        "BehaviorTest",
    ]
    _run_checked(command, "JUnit behavior validation")


def _run_checked(command: list[str], label: str) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise RuntimeError(f"{label} failed (exit {result.returncode}):\n{detail}")


def _classpath(toolchain: JavaToolchain, paths: Iterable[Path]) -> str:
    separator = ";" if toolchain.windows_paths_from_wsl or os.name == "nt" else os.pathsep
    return separator.join(_java_path(toolchain, path) for path in paths)


def _java_path(toolchain: JavaToolchain, path: Path) -> str:
    resolved = path.resolve()
    if toolchain.windows_paths_from_wsl:
        result = subprocess.run(
            ["wslpath", "-w", str(resolved)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    return str(resolved)


def _repository_path(dataset_root: Path, declared: str) -> Path:
    path = Path(declared)
    if path.is_absolute():
        candidate = path.resolve()
    else:
        candidate = (dataset_root.parents[1] / path).resolve()
    try:
        candidate.relative_to(dataset_root)
    except ValueError as exc:
        raise ValueError(f"Smoke fixture escapes the dataset root: {declared}") from exc
    return candidate


def _is_wsl() -> bool:
    return platform.system() == "Linux" and "microsoft" in platform.release().lower()


def _where_windows_executable(name: str) -> str | None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "where", name],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    first = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    return _wsl_path(first) if first else None


def _wsl_path(windows_path: str) -> str:
    result = subprocess.run(
        ["wslpath", "-u", windows_path.rstrip("\r")],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()
