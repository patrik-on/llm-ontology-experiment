from __future__ import annotations

import argparse
from pathlib import Path

from llm_ontology.data.format import read_records
from llm_ontology.data.group_split import (
    PartitionRecords,
    audit_group_disjointness,
    write_group_split_audit,
)
from llm_ontology.ingestion.manifest import GroupLevel, read_dataset_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit project/repository/commit identities across dataset roles and splits."
    )
    parser.add_argument(
        "--partition",
        action="append",
        required=True,
        metavar="MANIFEST=DATA",
        help="Repeat for retrieval, pilot validation and final benchmark partitions.",
    )
    parser.add_argument(
        "--group-level",
        choices=tuple(level.value for level in GroupLevel),
        default=GroupLevel.PROJECT.value,
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    partitions = []
    for value in args.partition:
        manifest_path, separator, data_path = value.partition("=")
        if not separator:
            raise ValueError(f"Invalid partition {value!r}; expected MANIFEST=DATA.")
        partitions.append(
            PartitionRecords(
                manifest=read_dataset_manifest(manifest_path),
                records=read_records(data_path),
            )
        )
    report = audit_group_disjointness(
        partitions, group_level=GroupLevel(args.group_level)
    )
    write_group_split_audit(report, Path(args.output))
    print(report.model_dump_json(indent=2))
    return 0 if report.safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
