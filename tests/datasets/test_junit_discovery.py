from __future__ import annotations

import os
from pathlib import Path

import pytest

from llm_ontology.benchmarks import smoke_validation


LOCK = (
    ("org/junit/jupiter", "junit-jupiter-api", "5.11.4"),
    ("org/junit/jupiter", "junit-jupiter-engine", "5.11.4"),
    ("org/junit/platform", "junit-platform-commons", "1.11.4"),
    ("org/junit/platform", "junit-platform-engine", "1.11.4"),
    ("org/junit/platform", "junit-platform-launcher", "1.11.4"),
    ("org/opentest4j", "opentest4j", "1.3.0"),
    ("org/apiguardian", "apiguardian-api", "1.1.2"),
)


def _jar(repository: Path, group: str, artifact: str, version: str) -> Path:
    path = repository / group / artifact / version / f"{artifact}-{version}.jar"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def _install(repository: Path) -> tuple[Path, ...]:
    return tuple(_jar(repository, *item) for item in LOCK)


@pytest.fixture(autouse=True)
def _isolated_repositories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SMOKE_JUNIT_CLASSPATH", raising=False)
    monkeypatch.setattr(
        smoke_validation, "_candidate_maven_repositories", lambda: iter((tmp_path,))
    )


def test_discovery_avoids_lexicographic_platform_version_trap(tmp_path: Path) -> None:
    expected = _install(tmp_path)
    for group, artifact, _ in LOCK:
        if group == "org/junit/platform":
            _jar(tmp_path, group, artifact, "1.9.3")
        elif group == "org/opentest4j":
            _jar(tmp_path, group, artifact, "1.2.0")
    # Classifier jars must not substitute for the pinned runtime artifacts.
    expected[0].with_name("junit-jupiter-api-5.11.4-sources.jar").touch()
    expected[0].with_name("junit-jupiter-api-5.11.4-javadoc.jar").touch()

    assert smoke_validation.discover_junit_classpath() == expected


def test_discovery_ignores_unapproved_newer_release(tmp_path: Path) -> None:
    expected = _install(tmp_path)
    _jar(tmp_path, "org/junit/jupiter", "junit-jupiter-api", "5.12.0")

    assert smoke_validation.discover_junit_classpath() == expected


@pytest.mark.parametrize("missing", range(len(LOCK)))
def test_discovery_rejects_each_incomplete_set(tmp_path: Path, missing: int) -> None:
    jars = _install(tmp_path)
    jars[missing].unlink()

    assert smoke_validation.discover_junit_classpath() == ()


def test_discovery_does_not_combine_incomplete_repositories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for index, item in enumerate(LOCK):
        _jar(first if index < 3 else second, *item)
    monkeypatch.setattr(
        smoke_validation, "_candidate_maven_repositories", lambda: iter((first, second))
    )

    assert smoke_validation.discover_junit_classpath() == ()


def test_discovery_skips_partial_repository_for_complete_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _jar(first, *LOCK[0])
    expected = _install(second)
    monkeypatch.setattr(
        smoke_validation, "_candidate_maven_repositories", lambda: iter((first, second))
    )

    assert smoke_validation.discover_junit_classpath() == expected


def test_discovery_rejects_complete_but_unpinned_set(tmp_path: Path) -> None:
    for group, artifact, version in LOCK:
        if group == "org/junit/jupiter":
            version = "5.10.0"
        elif group == "org/junit/platform":
            version = "1.10.0"
        _jar(tmp_path, group, artifact, version)

    assert smoke_validation.discover_junit_classpath() == ()


def test_valid_override_preserves_explicit_order_and_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    jars = tuple(reversed(_install(tmp_path / "override")))
    monkeypatch.setenv("SMOKE_JUNIT_CLASSPATH", os.pathsep.join(map(str, jars)))

    def no_cache_lookup():
        raise AssertionError("Explicit overrides must not inspect caches")

    monkeypatch.setattr(smoke_validation, "_candidate_maven_repositories", no_cache_lookup)

    assert smoke_validation.discover_junit_classpath() == jars


@pytest.mark.parametrize(
    "invalid",
    [
        "empty",
        "partial",
        "mixed_platform",
        "mixed_jupiter",
        "mixed_dependency",
        "missing_file",
        "directory",
        "duplicate",
        "extra",
        "empty_entry",
        "standalone",
    ],
)
def test_invalid_override_fails_closed_even_with_complete_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid: str
) -> None:
    _install(tmp_path)  # A valid cache must never mask an invalid explicit override.
    jars = list(_install(tmp_path / "override"))
    if invalid == "empty":
        jars = []
    elif invalid == "partial":
        jars.pop()
    elif invalid in {"mixed_platform", "mixed_jupiter", "mixed_dependency"}:
        index, version = {
            "mixed_platform": (2, "1.9.3"),
            "mixed_jupiter": (1, "5.10.0"),
            "mixed_dependency": (5, "1.2.0"),
        }[invalid]
        group, artifact, _ = LOCK[index]
        jars[index] = _jar(tmp_path / "override", group, artifact, version)
    elif invalid == "missing_file":
        jars[0].unlink()
    elif invalid == "directory":
        jars[0].unlink()
        jars[0].mkdir()
    elif invalid == "duplicate":
        jars[-1] = jars[0]
    elif invalid == "extra":
        jars.append(
            _jar(tmp_path / "override", "org/junit/jupiter", "junit-jupiter-params", "5.11.4")
        )
    elif invalid == "standalone":
        jars = [
            _jar(
                tmp_path / "override",
                "org/junit/platform",
                "junit-platform-console-standalone",
                "1.11.4",
            )
        ]
    override = os.pathsep.join(map(str, jars))
    if invalid == "empty_entry":
        override += os.pathsep
    monkeypatch.setenv("SMOKE_JUNIT_CLASSPATH", override)

    with pytest.raises(ValueError, match="SMOKE_JUNIT_CLASSPATH.*pinned jars"):
        smoke_validation.discover_junit_classpath()
