from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_ontology.providers.contracts import EmbeddingProvider


class CollectionManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    collection_name: str
    embedding_model: str
    embedding_revision: str | None
    embedding_remote_code_revision: str | None = None
    embedding_dimension: int
    embedding_normalized: bool
    embedding_template_version: str
    chunker_name: str
    chunker_version: str
    ingestion_pipeline_version: str
    dataset_manifests: list[str]
    document_count: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    library_versions: dict[str, str] = Field(default_factory=dict)


class IncompatibleCollectionError(RuntimeError):
    pass


class CollectionManifestStore:
    """Sidecar lifecycle guard preventing silent reuse of stale Chroma indexes."""

    COMPATIBILITY_FIELDS = (
        "collection_name",
        "embedding_model",
        "embedding_revision",
        "embedding_remote_code_revision",
        "embedding_dimension",
        "embedding_normalized",
        "embedding_template_version",
        "chunker_name",
        "chunker_version",
        "ingestion_pipeline_version",
        "dataset_manifests",
        "library_versions",
    )

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, collection_name: str) -> Path:
        return self.root / "manifests" / f"{collection_name}.json"

    def write(self, manifest: CollectionManifest) -> Path:
        path = self.path_for(manifest.collection_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    def read(self, collection_name: str) -> CollectionManifest:
        path = self.path_for(collection_name)
        if not path.exists():
            raise IncompatibleCollectionError(
                f"Collection {collection_name!r} has no manifest. "
                "Rebuild explicitly through CollectionIndexLifecycle.rebuild()."
            )
        return CollectionManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def require_compatible(
        self, collection_name: str, expected: CollectionManifest
    ) -> CollectionManifest:
        actual = self.read(collection_name)
        mismatches = _manifest_mismatches(actual, expected, self.COMPATIBILITY_FIELDS)
        if mismatches:
            details = "; ".join(
                f"{field}: index={values[0]!r}, configured={values[1]!r}"
                for field, values in mismatches.items()
            )
            raise IncompatibleCollectionError(
                f"Collection {collection_name!r} is incompatible: {details}. "
                "Rebuild explicitly through CollectionIndexLifecycle.rebuild()."
            )
        return actual

    def remove(self, collection_name: str) -> None:
        path = self.path_for(collection_name)
        if path.exists():
            path.unlink()


def create_collection_manifest(
    *,
    collection_name: str,
    embedding_provider: EmbeddingProvider,
    embedding_normalized: bool,
    embedding_template_version: str,
    chunker_name: str,
    chunker_version: str,
    ingestion_pipeline_version: str,
    dataset_manifests: list[str],
    document_count: int = 0,
) -> CollectionManifest:
    library_versions = getattr(embedding_provider, "library_versions", {})
    return CollectionManifest(
        collection_name=collection_name,
        embedding_model=embedding_provider.model_identifier,
        embedding_revision=embedding_provider.model_revision,
        embedding_remote_code_revision=getattr(
            embedding_provider, "remote_code_revision", None
        ),
        embedding_dimension=embedding_provider.embedding_dimension,
        embedding_normalized=embedding_normalized,
        embedding_template_version=embedding_template_version,
        chunker_name=chunker_name,
        chunker_version=chunker_version,
        ingestion_pipeline_version=ingestion_pipeline_version,
        dataset_manifests=dataset_manifests,
        document_count=document_count,
        library_versions=dict(library_versions),
    )


def _manifest_mismatches(
    actual: CollectionManifest,
    expected: CollectionManifest,
    fields: tuple[str, ...],
) -> dict[str, tuple[Any, Any]]:
    mismatches = {}
    for field in fields:
        actual_value = getattr(actual, field)
        expected_value = getattr(expected, field)
        if field == "dataset_manifests":
            actual_value = sorted(actual_value)
            expected_value = sorted(expected_value)
        if actual_value != expected_value:
            mismatches[field] = (actual_value, expected_value)
    return mismatches
