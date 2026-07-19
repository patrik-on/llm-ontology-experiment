from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


PUBLIC_CLASS_PATTERN = re.compile(
    r"\bpublic\s+(?:(?:abstract|final|static|strictfp)\s+)*class\s+([A-Za-z_$][A-Za-z0-9_$]*)"
)
CLASS_PATTERN = re.compile(r"\bclass\s+([A-Za-z_$][A-Za-z0-9_$]*)")
PACKAGE_PATTERN = re.compile(r"^\s*package\s+[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*;", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class TestBenchExecutionPlan:
    case_id: str
    project: str
    build_root: Path
    test_directory: Path
    test_file: Path
    test_class: str
    package: str
    code: str
    maven_args: tuple[str, ...]
    java_home: Path | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "project": self.project,
            "build_root": str(self.build_root),
            "test_file": str(self.test_file),
            "test_class": self.test_class,
            "package": self.package,
            "maven_args": list(self.maven_args),
            "java_home": str(self.java_home) if self.java_home else None,
        }


def strip_markdown_fence(text: str) -> str:
    value = text.strip()
    fenced = re.search(r"```(?:java)?\s*\n?(.*?)```", value, re.IGNORECASE | re.DOTALL)
    return fenced.group(1).strip() if fenced else value


def generated_class_name(code: str) -> str:
    match = PUBLIC_CLASS_PATTERN.search(code) or CLASS_PATTERN.search(code)
    if not match:
        raise ValueError("Generated prediction does not contain a Java class declaration.")
    return match.group(1)


def _resolve_within(root: Path, relative: str, *, label: str) -> Path:
    normalized = PurePosixPath(relative.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Unsafe {label} path: {relative!r}")
    root = root.resolve()
    candidate = root.joinpath(*normalized.parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"{label} escapes benchmark root: {relative!r}")
    return candidate


def _test_source_directory(benchmark_root: Path, relative_source: str) -> Path:
    parts = list(PurePosixPath(relative_source.replace("\\", "/")).parts)
    replacement_index = -1
    for index in range(len(parts) - 2):
        if parts[index : index + 3] == ["src", "main", "java"]:
            replacement_index = index
            break
    if replacement_index < 0:
        raise ValueError(f"Source path does not contain src/main/java: {relative_source!r}")
    parts[replacement_index + 1] = "test"
    test_source = "/".join(parts)
    return _resolve_within(benchmark_root, str(PurePosixPath(test_source).parent), label="test source")


def _java_home_for_project(
    project: str,
    default_java_home: str | Path | None,
    project_java_homes: Mapping[str, str | Path] | None,
) -> Path | None:
    selected = (project_java_homes or {}).get(project, default_java_home)
    return Path(selected).expanduser().resolve() if selected else None


def plan_testbench_record(
    record: Mapping[str, Any],
    *,
    benchmark_root: str | Path,
    default_java_home: str | Path | None = None,
    project_java_homes: Mapping[str, str | Path] | None = None,
    repair_package: bool = False,
) -> TestBenchExecutionPlan:
    if str(record.get("benchmark", "")) != "testbench":
        raise ValueError("Prediction record is not from TestBench.")
    prediction = strip_markdown_fence(str(record.get("prediction", "")))
    if not prediction:
        raise ValueError("Prediction record has no generated test code.")
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("Prediction record metadata must be an object.")

    root = Path(benchmark_root).resolve()
    project = str(metadata.get("project", "")).strip()
    package = str(metadata.get("package", "")).strip()
    if not project or not package:
        raise ValueError("TestBench metadata must contain project and package.")
    if repair_package and not PACKAGE_PATTERN.search(prediction):
        prediction = f"package {package};\n\n{prediction}"
    test_class = generated_class_name(prediction)
    build_root = _resolve_within(root, str(metadata.get("execute_path", "")), label="build root")
    if not (build_root / "pom.xml").is_file():
        raise FileNotFoundError(f"Maven pom.xml is missing in {build_root}")
    test_directory = _test_source_directory(root, str(metadata.get("relative_path", "")))
    test_file = test_directory / f"{test_class}.java"
    if root != test_file.resolve() and root not in test_file.resolve().parents:
        raise ValueError(f"Generated test path escapes benchmark root: {test_file}")

    maven_args = (
        "-B",
        "-ntp",
        "-DskipPitest=true",
        "-Drat.skip=true",
        "-Dsurefire.failIfNoSpecifiedTests=false",
        "-DfailIfNoTests=false",
        "-Dcheckstyle.skip=true",
        f"-Dtest={test_class}",
        "test",
    )
    return TestBenchExecutionPlan(
        case_id=str(record.get("id", "")),
        project=project,
        build_root=build_root,
        test_directory=test_directory,
        test_file=test_file,
        test_class=test_class,
        package=package,
        code=prediction,
        maven_args=maven_args,
        java_home=_java_home_for_project(project, default_java_home, project_java_homes),
    )


def _resolve_maven(executable: str) -> Path:
    candidate = Path(executable)
    if candidate.parent != Path(".") or candidate.is_absolute():
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    discovered = shutil.which(executable)
    if not discovered:
        raise FileNotFoundError(f"Maven executable was not found: {executable}")
    return Path(discovered).resolve()


def _platform_command(maven: Path, args: tuple[str, ...]) -> list[str]:
    if os.name == "nt" and maven.suffix.lower() in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", str(maven), *args]
    return [str(maven), *args]


def _status_for_process(return_code: int, output: str) -> str:
    if return_code == 0:
        return "accepted"
    if "COMPILATION ERROR" in output or "testCompile" in output:
        return "compile_error"
    if re.search(r"Failures:\s*[1-9]|Errors:\s*[1-9]", output):
        return "test_error"
    return "maven_error"


def execute_testbench_plan(
    plan: TestBenchExecutionPlan,
    *,
    maven_executable: str = "mvn",
    timeout_seconds: int = 300,
    dry_run: bool = False,
) -> dict[str, Any]:
    result = plan.as_dict()
    if dry_run:
        result.update({"status": "planned", "return_code": None, "duration_seconds": 0.0})
        return result

    maven = _resolve_maven(maven_executable)
    command = _platform_command(maven, plan.maven_args)
    environment = os.environ.copy()
    if plan.java_home:
        java_executable = plan.java_home / "bin" / ("java.exe" if os.name == "nt" else "java")
        if not java_executable.is_file():
            raise FileNotFoundError(f"JAVA_HOME does not contain bin/java: {plan.java_home}")
        environment["JAVA_HOME"] = str(plan.java_home)
        environment["PATH"] = str(plan.java_home / "bin") + os.pathsep + environment.get("PATH", "")

    plan.test_directory.mkdir(parents=True, exist_ok=True)
    original = plan.test_file.read_bytes() if plan.test_file.exists() else None
    started = time.monotonic()
    try:
        plan.test_file.write_text(plan.code, encoding="utf-8")
        try:
            completed = subprocess.run(
                command,
                cwd=plan.build_root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            output = f"{completed.stdout}\n{completed.stderr}".strip()
            result.update(
                {
                    "status": _status_for_process(completed.returncode, output),
                    "return_code": completed.returncode,
                    "output_tail": output[-12000:],
                    "command": command,
                }
            )
        except subprocess.TimeoutExpired as exc:
            output = f"{exc.stdout or ''}\n{exc.stderr or ''}".strip()
            result.update(
                {
                    "status": "timeout",
                    "return_code": None,
                    "output_tail": output[-12000:],
                    "command": command,
                }
            )
    finally:
        if original is None:
            plan.test_file.unlink(missing_ok=True)
        else:
            plan.test_file.write_bytes(original)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def read_prediction_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}")
            records.append(payload)
    return records


def parse_project_java_homes(values: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        project, separator, path = value.partition("=")
        if not separator or not project.strip() or not path.strip():
            raise ValueError(f"Expected PROJECT=PATH for project JAVA_HOME, got {value!r}")
        mapping[project.strip()] = path.strip()
    return mapping
