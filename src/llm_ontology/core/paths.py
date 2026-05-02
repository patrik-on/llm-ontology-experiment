from __future__ import annotations

from pathlib import Path
from typing import Iterable


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
