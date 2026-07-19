from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ResponseEvaluator(Protocol):
    def evaluate(
        self,
        *,
        task: str,
        response: str,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a generated response without depending on its provider."""
