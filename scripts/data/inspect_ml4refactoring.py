from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.data.ml4refactoring import DEFAULT_DATASET_DIR, DEFAULT_TEMP_DIR, inspect_ml4refactoring


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ML4Refactoring project ZIP structure.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--project-zip", default=None)
    parser.add_argument("--max-projects", type=int, default=None)
    parser.add_argument("--temp-dir", default=str(DEFAULT_TEMP_DIR))
    args = parser.parse_args()

    inspection = inspect_ml4refactoring(
        dataset_dir=args.dataset_dir,
        project_zip=args.project_zip,
        max_projects=args.max_projects,
        temp_dir=args.temp_dir,
    )

    print("ML4Refactoring inspection")
    print(f"Dataset directory: {inspection.dataset_dir}")
    print(f"Project ZIP count: {inspection.project_zip_count}")
    print("\nFirst project ZIPs:")
    for path, size in inspection.first_project_zips:
        print(f"- {path.name}: {format_size(size)}")

    print("\nInspected project ZIP:")
    print(f"- ZIP: {inspection.inspected_zip}")
    print(f"- Project name: {inspection.project_name}")
    print(f"- Commit directories: {inspection.commit_count}")
    print(f"- Commits with before/after dirs: {inspection.before_after_commit_count}")
    print(f"- Candidate files: {inspection.candidate_file_count}")

    print("\nSample file names:")
    for name in inspection.sample_files:
        print(f"- {name}")

    print("\nSample refactoring types:")
    for name, refactoring_type in inspection.sample_refactoring_types:
        print(f"- {name}: {refactoring_type}")


if __name__ == "__main__":
    main()
