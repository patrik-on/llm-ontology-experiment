from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVALUATION_RUNS_ROOT = Path("artifacts/evaluation/runs")
RUN_MANIFEST_SCHEMA_VERSION = "1"
_RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def validate_evaluation_run_id(run_id: str) -> str:
    normalized = run_id.strip()
    if not _RUN_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Evaluation run_id must contain 2-64 lowercase letters, numbers, dots, "
            "underscores or hyphens, and cannot contain a path separator."
        )
    return normalized


def require_canonical_evaluation_path(path: str | Path) -> Path:
    """Reject CLI output paths outside the canonical evaluation runs namespace."""

    runs_root = EVALUATION_RUNS_ROOT.resolve()
    candidate = Path(path).resolve()
    try:
        relative = candidate.relative_to(runs_root)
    except ValueError as exc:
        raise ValueError(
            f"Evaluation output must be inside {EVALUATION_RUNS_ROOT.as_posix()}/."
        ) from exc
    if not relative.parts:
        raise ValueError("Evaluation output must identify a run_id below the runs root.")
    validate_evaluation_run_id(relative.parts[0])
    return candidate


@dataclass(frozen=True, slots=True)
class EvaluationRunLayout:
    """Canonical, repository-local filesystem contract for one evaluation run."""

    run_id: str
    runs_root: Path = EVALUATION_RUNS_ROOT

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", validate_evaluation_run_id(self.run_id))

    @property
    def root(self) -> Path:
        return self.runs_root / self.run_id

    @property
    def predictions(self) -> Path:
        return self.root / "predictions"

    @property
    def metrics(self) -> Path:
        return self.root / "metrics"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def samples(self) -> Path:
        return self.root / "samples"

    @property
    def analysis(self) -> Path:
        return self.root / "analysis"

    @property
    def manifest_path(self) -> Path:
        return self.root / "run_manifest.json"

    def prepare(self) -> None:
        for path in (
            self.predictions,
            self.metrics,
            self.reports,
            self.samples,
            self.analysis,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def write_manifest(
        self,
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        self.prepare()
        now = datetime.now(timezone.utc).isoformat()
        previous: dict[str, Any] = {}
        if self.manifest_path.exists():
            previous = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        payload = {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "artifact_type": "evaluation_run",
            "run_id": self.run_id,
            "status": status,
            "created_at": previous.get("created_at", now),
            "updated_at": now,
            "path": self.root.as_posix(),
            "layout": {
                "predictions": "predictions",
                "metrics": "metrics",
                "reports": "reports",
                "samples": "samples",
                "analysis": "analysis",
            },
            "metadata": {**previous.get("metadata", {}), **(metadata or {})},
        }
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.manifest_path)
        return self.manifest_path
