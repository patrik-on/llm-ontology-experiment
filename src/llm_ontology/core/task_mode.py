from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class CanonicalTask(StrEnum):
    REFACTORING = "refactoring"
    TESTING = "testing"


TASK_ALIASES: dict[str, CanonicalTask] = {
    "refactor": CanonicalTask.REFACTORING,
    "refactoring": CanonicalTask.REFACTORING,
    "test_generation": CanonicalTask.TESTING,
    "testing": CanonicalTask.TESTING,
}


class ResolvedTask(BaseModel):
    requested: str
    canonical: CanonicalTask


def resolve_task(value: str) -> ResolvedTask:
    requested = value.strip().lower().replace("-", "_")
    try:
        canonical = TASK_ALIASES[requested]
    except KeyError as exc:
        supported = ", ".join(sorted(TASK_ALIASES))
        raise ValueError(f"Unsupported task {value!r}. Supported values: {supported}.") from exc
    return ResolvedTask(requested=requested, canonical=canonical)
