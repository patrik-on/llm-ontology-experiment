from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

# Machine-specific roots. Configs refer to them as ``${NAME}`` so the repository
# itself contains no absolute paths of one computer. Defaults match the original
# WSL layout; override them with environment variables (see ``.env.example``).
ENV_ROOT_DEFAULTS = {
    "LLM_ONTOLOGY_WORK_ROOT": "~/benchmark-work",
    "LLM_ONTOLOGY_MODELS_ROOT": "/mnt/c/models",
    "LLM_ONTOLOGY_DATASETS_ROOT": "/mnt/c/datasets",
}
_PLACEHOLDER = re.compile(r"\$\{(LLM_ONTOLOGY_[A-Z_]+)\}")


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_path(path: str | Path, root: str | Path | None = None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (Path(root) if root else project_root()) / candidate


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_parent(path: str | Path) -> Path:
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def ensure_output_dirs(config: dict) -> None:
    for key in ("adapter_dir", "checkpoint_dir", "result_dir"):
        if key in config.get("output", {}):
            ensure_dir(resolve_path(config["output"][key]))


def existing_files(paths: Iterable[str | Path]) -> list[Path]:
    return [Path(path) for path in paths if Path(path).exists()]


def env_root(name: str) -> str:
    """Return a configured machine-specific root directory as a string."""
    if name not in ENV_ROOT_DEFAULTS:
        raise KeyError(f"Unknown path variable: {name}")
    value = os.environ.get(name) or ENV_ROOT_DEFAULTS[name]
    return str(Path(value).expanduser()).rstrip("/") or "/"


def work_root_path(*parts: str) -> Path:
    """Path under ``LLM_ONTOLOGY_WORK_ROOT`` (default ``~/benchmark-work``)."""
    return Path(env_root("LLM_ONTOLOGY_WORK_ROOT"), *parts)


def expand_placeholders(value: Any) -> Any:
    """Expand only ``${LLM_ONTOLOGY_*}`` placeholders in nested config values.

    Other ``$`` text (for example in Java sources stored in JSON) is untouched.
    """
    if isinstance(value, str):
        return _PLACEHOLDER.sub(lambda m: env_root(m.group(1)), value)
    if isinstance(value, dict):
        return {key: expand_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_placeholders(item) for item in value]
    return value
