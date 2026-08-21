from __future__ import annotations

from collections.abc import Mapping


def build_retrieval_query(
    *,
    strategy: str,
    task: str,
    input_text: str,
    requirements: str = "",
    structured_identity: Mapping[str, str] | None = None,
) -> str:
    """Build a query only from information already visible in the model prompt."""

    if strategy == "raw_input":
        return input_text.strip()
    if strategy != "task_aware_v1":
        raise ValueError(f"Unsupported retrieval query strategy: {strategy!r}")
    if task not in {"testing", "refactoring"}:
        raise ValueError(f"Unsupported retrieval task: {task!r}")

    identity = structured_identity or {}
    task_label = "test generation" if task == "testing" else "refactoring"
    source_heading = (
        "Production Java code" if task == "testing" else "Original Java code"
    )
    parts = [f"Task: {task_label}"]
    class_name = str(identity.get("class_name", "")).strip()
    focal_method = str(
        identity.get("focal_method", identity.get("focal_method_name", ""))
    ).strip()
    if class_name:
        parts.append(f"Java class: {class_name}")
    if focal_method:
        parts.append(f"Focal method: {focal_method}")
    if requirements.strip():
        parts.append(f"Requirements: {requirements.strip()}")
    parts.append(f"{source_heading}:\n{input_text.strip()}")
    return "\n\n".join(parts)
