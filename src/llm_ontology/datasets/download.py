from __future__ import annotations

from pathlib import Path


SUPPORTED_DATA_EXTENSIONS = {".jsonl", ".json", ".csv"}


def list_data_files(raw_dir: str | Path) -> list[Path]:
    directory = Path(raw_dir)
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_DATA_EXTENSIONS
    )


def assert_raw_data_available(raw_dir: str | Path, dataset_name: str) -> list[Path]:
    files = list_data_files(raw_dir)
    if not files:
        raise FileNotFoundError(
            f"No raw {dataset_name} files found in {raw_dir}. "
            "Add JSONL, JSON, or CSV files before preparing data."
        )
    return files
