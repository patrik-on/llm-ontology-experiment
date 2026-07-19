from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from llm_ontology.benchmarks.testbench import load_testbench


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _tool_check(name: str) -> ReadinessCheck:
    path = shutil.which(name)
    return ReadinessCheck(name, "pass" if path else "fail", path or f"{name} is not available on PATH")


def _java_home_check(label: str, value: str | Path | None) -> ReadinessCheck:
    if not value:
        return ReadinessCheck(label, "fail", "not configured")
    root = Path(value).expanduser().resolve()
    executable = root / "bin" / ("java.exe" if os.name == "nt" else "java")
    return ReadinessCheck(label, "pass" if executable.is_file() else "fail", str(root))


def _ollama_check(base_url: str, model_name: str) -> ReadinessCheck:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError) as exc:
        return ReadinessCheck("ollama", "fail", f"not reachable at {base_url}: {exc}")
    names = {str(item.get("name", "")) for item in payload.get("models", []) if isinstance(item, dict)}
    matches = model_name in names or any(name.split(":", 1)[0] == model_name.split(":", 1)[0] for name in names)
    return ReadinessCheck(
        "ollama_model",
        "pass" if matches else "fail",
        f"requested={model_name}; available={sorted(names)}",
    )


def check_testbench_readiness(
    *,
    root: str | Path = "benchmarks/TestBench-main",
    backend: str = "ollama",
    model_name: str = "qwen2.5-coder:7b",
    base_url: str = "http://localhost:11434",
    java_home: str | Path | None = None,
    java17_home: str | Path | None = None,
) -> list[ReadinessCheck]:
    benchmark_root = Path(root).resolve()
    checks: list[ReadinessCheck] = []
    try:
        cases = load_testbench(benchmark_root)
        valid = len(cases) == 108 and len({case.case_id for case in cases}) == 108
        checks.append(ReadinessCheck("testbench_data", "pass" if valid else "fail", f"cases={len(cases)}"))
        build_roots = {str(case.metadata.get("execute_path", "")) for case in cases}
        missing = sorted(path for path in build_roots if not (benchmark_root / path / "pom.xml").is_file())
        checks.append(
            ReadinessCheck(
                "maven_projects",
                "pass" if not missing else "fail",
                f"roots={len(build_roots)}; missing_poms={missing}",
            )
        )
        checks.append(
            ReadinessCheck(
                "benchmark_writable",
                "pass" if os.access(benchmark_root, os.W_OK) else "fail",
                str(benchmark_root),
            )
        )
    except Exception as exc:
        checks.append(ReadinessCheck("testbench_data", "fail", str(exc)))

    checks.append(_tool_check("mvn"))
    checks.append(_java_home_check("legacy_java_home", java_home))
    checks.append(_java_home_check("java17_home", java17_home))
    jdk_ready = bool(java_home and java17_home)
    checks.append(
        ReadinessCheck(
            "jdk_matrix",
            "pass" if jdk_ready else "fail",
            "legacy projects target Java 6/7/8; project 'Java' targets Java 17",
        )
    )
    free_gib = shutil.disk_usage(benchmark_root).free / (1024**3)
    checks.append(ReadinessCheck("disk_space", "pass" if free_gib >= 5 else "warn", f"free_gib={free_gib:.1f}"))
    checks.append(
        ReadinessCheck(
            "maven_dependencies",
            "warn",
            "first execution needs network access to populate the Maven cache; legacy repositories may need fixes",
        )
    )
    if backend == "ollama":
        checks.append(_ollama_check(base_url, model_name))
    elif backend != "prompt-only":
        checks.append(ReadinessCheck("backend", "fail", f"unsupported backend: {backend}"))
    return checks


def is_ready(checks: list[ReadinessCheck]) -> bool:
    return all(check.status != "fail" for check in checks)


def checks_as_json(checks: list[ReadinessCheck]) -> dict[str, Any]:
    return {"ready": is_ready(checks), "checks": [check.as_dict() for check in checks]}
