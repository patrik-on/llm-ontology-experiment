"""Shared pytest markers.

Some tests exercise the real experiment inputs that are deliberately kept out of
Git (large datasets, local audit evidence) or optional extras. They are marked
and skipped with an explicit reason when the input is unavailable, so a fresh
clone runs green while the full local setup still executes every test.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Git-ignored inputs required by the refactoring matrix plan (see
# configs/benchmarks/refactoring_matrix_v1.json and docs/thesis/reproducible_handoff.md).
LOCAL_DATA = (
    "benchmarks/swe-refactor/SWE-Refactor/pure_refactoring_data.json",
    "artifacts/swe_overlap_audit_20261113/case_matches.json",
    "artifacts/swe_overlap_audit_20261113/report.json",
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "local_data: needs Git-ignored local datasets/audit evidence (skipped if absent)"
    )
    config.addinivalue_line("markers", "rag: needs the `rag` extra (chromadb)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    missing = [path for path in LOCAL_DATA if not (REPO / path).is_file()]
    no_chroma = importlib.util.find_spec("chromadb") is None
    for item in items:
        if missing and item.get_closest_marker("local_data"):
            item.add_marker(pytest.mark.skip(reason="missing local data: " + ", ".join(missing)))
        if no_chroma and item.get_closest_marker("rag"):
            item.add_marker(pytest.mark.skip(reason='chromadb not installed (pip install -e ".[rag]")'))
