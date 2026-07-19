from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


class EnvironmentCheck(BaseModel):
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    detail: str = ""


class EnvironmentCheckReport(BaseModel):
    lock_path: str
    checks: list[EnvironmentCheck] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)

    def require_ready(self) -> None:
        if not self.ready:
            failed = "; ".join(check.name for check in self.checks if not check.passed)
            raise RuntimeError(f"Experiment environment does not match its lock: {failed}.")


def verify_environment_lock(
    lock_path: str | Path,
    *,
    check_ollama: bool = True,
    check_benchmark_toolchain: bool = False,
    opener: Callable[..., Any] = urlopen,
) -> EnvironmentCheckReport:
    path = Path(lock_path)
    lock = json.loads(path.read_text(encoding="utf-8"))
    checks = [
        EnvironmentCheck(
            name="python_version",
            passed=_python_version() == lock["python"]["version"],
            expected=lock["python"]["version"],
            actual=_python_version(),
        )
    ]
    requirements_path = Path(lock["python_packages_lock"])
    if not requirements_path.is_absolute():
        repository_candidate = path.parents[2] / requirements_path
        requirements_path = (
            repository_candidate if repository_candidate.exists() else requirements_path
        )
    actual_hash = hashlib.sha256(requirements_path.read_bytes()).hexdigest()
    expected_hash = str(lock["python_packages_lock_sha256"]).lower()
    checks.append(
        EnvironmentCheck(
            name="python_packages_lock_hash",
            passed=actual_hash == expected_hash,
            expected=expected_hash,
            actual=actual_hash,
        )
    )
    expected_packages = _read_requirements_lock(requirements_path)
    installed = {
        _canonical_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    }
    mismatches = {
        name: {"expected": version, "actual": installed.get(name)}
        for name, version in expected_packages.items()
        if installed.get(name) != version
    }
    checks.append(
        EnvironmentCheck(
            name="python_packages",
            passed=not mismatches,
            expected=f"{len(expected_packages)} exact package versions",
            actual=mismatches or "all locked packages match",
        )
    )
    if check_ollama:
        checks.extend(_verify_ollama(lock["ollama"], opener))
    if check_benchmark_toolchain:
        checks.extend(_verify_benchmark_toolchain(lock["benchmark_toolchain"]))
    return EnvironmentCheckReport(lock_path=path.as_posix(), checks=checks)


def _verify_ollama(
    expected: dict[str, Any], opener: Callable[..., Any]
) -> list[EnvironmentCheck]:
    try:
        version = _get_json(expected["base_url"] + "/api/version", opener)["version"]
        models = _get_json(expected["base_url"] + "/api/tags", opener).get("models", [])
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        return [
            EnvironmentCheck(
                name="ollama_runtime",
                passed=False,
                expected=expected["base_url"],
                actual=None,
                detail=str(exc),
            )
        ]
    model = next(
        (
            item
            for item in models
            if item.get("name") == expected["model"] or item.get("model") == expected["model"]
        ),
        None,
    )
    actual_digest = None if model is None else model.get("digest")
    expected_digest = expected.get("runtime_digest")
    return [
        EnvironmentCheck(
            name="ollama_version",
            passed=version == expected["version"],
            expected=expected["version"],
            actual=version,
        ),
        EnvironmentCheck(
            name="ollama_model_digest",
            passed=bool(expected_digest) and actual_digest == expected_digest,
            expected=expected_digest,
            actual=actual_digest,
            detail=(
                "The lock is incomplete until qwen2.5-coder:7b is installed and its digest is frozen."
                if not expected_digest
                else ""
            ),
        ),
    ]


def _get_json(url: str, opener: Callable[..., Any]) -> dict[str, Any]:
    request = Request(url, method="GET")
    with opener(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {url}.")
    return payload


def _verify_benchmark_toolchain(expected: dict[str, Any]) -> list[EnvironmentCheck]:
    actual = {
        "java_on_path": shutil.which("java") is not None,
        "maven_on_path": shutil.which("mvn") is not None,
        "testbench_java8_home_set": bool(os.environ.get("TESTBENCH_JAVA8_HOME")),
        "testbench_java17_home_set": bool(os.environ.get("TESTBENCH_JAVA17_HOME")),
    }
    checks = []
    for name, present in actual.items():
        checks.append(
            EnvironmentCheck(
                name=name,
                passed=present and bool(expected.get(name)),
                expected=True,
                actual=present,
                detail="Required only for Java benchmark execution.",
            )
        )
    return checks


def _read_requirements_lock(path: Path) -> dict[str, str]:
    packages = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        name, separator, version = value.partition("==")
        if not separator:
            raise ValueError(f"Non-exact requirement in environment lock: {value}")
        packages[_canonical_name(name)] = version
    return packages


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _python_version() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])
