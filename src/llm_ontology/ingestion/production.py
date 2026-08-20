from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from llm_ontology.data.format import read_records, write_jsonl
from llm_ontology.data.group_split import (
    PartitionRecords,
    audit_group_disjointness,
    record_group_key,
    write_group_split_audit,
)
from llm_ontology.ingestion.corpus import ProductionCorpusBuilder
from llm_ontology.ingestion.identity import (
    SampleFingerprint,
    detect_leakage,
    java_code_hash,
    write_fingerprints,
    write_leakage_report,
)
from llm_ontology.ingestion.loaders import NormalizedJsonlLoader
from llm_ontology.ingestion.java import SafeJavaSignatureParser
from llm_ontology.ingestion.manifest import (
    GroupLevel,
    UsageRole,
    create_dataset_manifest,
    read_dataset_manifest,
    write_dataset_manifest,
)
from llm_ontology.retrieval.config import RagConfig
from llm_ontology.retrieval.factory import create_vector_store
from llm_ontology.retrieval.models import DocumentChunk, sha256_text
from llm_ontology.vectorstore.lifecycle import CollectionIndexLifecycle
from llm_ontology.vectorstore.contracts import IndexWriteResult
from llm_ontology.vectorstore.manifest import (
    IncompatibleCollectionError,
    create_collection_manifest,
)


class ProductionCollectionReport(BaseModel):
    collection: str
    received: int
    indexed: int
    duplicates: int
    source_type_distribution: dict[str, int]
    dataset_manifest_ids: list[str]
    collection_manifest_path: str
    document_ids_digest: str
    embedding_source: str


class ProductionIndexReport(BaseModel):
    pipeline_version: str
    embedding_provider: str
    embedding_model: str
    embedding_revision: str | None
    embedding_model_digest: str | None = None
    literature_status: str
    retrieval_documents: int
    benchmark_documents: int
    selection_exclusions: dict[str, dict[str, int]]
    derived_manifest_paths: dict[str, str]
    group_audit_paths: list[str]
    leakage_audit_paths: list[str]
    equivalent_corpus: bool
    collections: list[ProductionCollectionReport] = Field(default_factory=list)


def build_production_indexes(
    config: RagConfig,
    *,
    testing_retrieval_manifest: str | Path,
    refactoring_retrieval_manifest: str | Path,
    testing_benchmark_manifest: str | Path,
    refactoring_benchmark_manifest: str | Path,
    root: str | Path = ".",
) -> ProductionIndexReport:
    """Audit, materialize, and explicitly rebuild equivalent production indexes."""

    project_root = Path(root).resolve()
    manifests = {
        "testing_retrieval": read_dataset_manifest(testing_retrieval_manifest),
        "refactoring_retrieval": read_dataset_manifest(
            refactoring_retrieval_manifest
        ),
        "testing_benchmark": read_dataset_manifest(testing_benchmark_manifest),
        "refactoring_benchmark": read_dataset_manifest(
            refactoring_benchmark_manifest
        ),
    }
    paths = {
        name: manifest.require_source_matches(root=project_root)
        for name, manifest in manifests.items()
    }
    for name in ("testing_retrieval", "refactoring_retrieval"):
        manifests[name].require_indexable()

    audit_root = project_root / "artifacts" / "split_audits"
    corpus_root = project_root / "artifacts" / "indexes" / "production_corpus"
    raw_records = {name: read_records(path) for name, path in paths.items()}
    group_audit_paths = []
    selection_exclusions = {}
    derived_manifest_paths = {}
    for task, group_level in (
        ("testing", GroupLevel.PROJECT),
        ("refactoring", GroupLevel.METHOD),
    ):
        retrieval_name = f"{task}_retrieval"
        benchmark_name = f"{task}_benchmark"
        selected, identity_excluded, fingerprint_excluded = _select_disjoint_records(
            raw_records[retrieval_name],
            raw_records[benchmark_name],
            group_level=group_level,
        )
        selection_exclusions[task] = {
            "identity": identity_excluded,
            "code_fingerprint": fingerprint_excluded,
            "total": identity_excluded + fingerprint_excluded,
        }
        selected_path = corpus_root / f"{task}_retrieval.jsonl"
        write_jsonl(selected, selected_path)
        source_manifest = manifests[retrieval_name]
        derived_manifest = create_dataset_manifest(
            selected_path,
            dataset_name=f"{source_manifest.dataset_name}_leakage_safe",
            dataset_version=(
                f"{source_manifest.dataset_version}+{group_level.value}-disjoint-v1"
            ),
            source_split="train",
            usage_role=UsageRole.RETRIEVAL,
            allowed_for_indexing=True,
            sample_count=len(selected),
            metadata={
                **source_manifest.metadata,
                "upstream_manifest_id": source_manifest.manifest_id,
                "selection_policy": (
                    f"exclude retrieval {group_level.value} identities present "
                    "in the final benchmark"
                ),
                "excluded_records": identity_excluded + fingerprint_excluded,
                "identity_excluded_records": identity_excluded,
                "code_fingerprint_excluded_records": fingerprint_excluded,
            },
            fingerprints_path=(
                f"artifacts/split_audits/{task}_retrieval_fingerprints.jsonl"
            ),
            grouping_policy=source_manifest.grouping_policy,
        ).model_copy(
            update={"source_path": selected_path.relative_to(project_root).as_posix()}
        )
        derived_path = corpus_root / f"{task}_retrieval.manifest.json"
        write_dataset_manifest(derived_manifest, derived_path)
        manifests[retrieval_name] = derived_manifest
        paths[retrieval_name] = selected_path
        raw_records[retrieval_name] = selected
        derived_manifest_paths[task] = derived_path.as_posix()

        group_audit_path = audit_root / (
            f"{task}_retrieval_vs_benchmark_{group_level.value}s_post_filter.json"
        )
        group_report = audit_group_disjointness(
            [
                PartitionRecords(
                    manifest=manifests[f"{task}_{role}"],
                    records=raw_records[f"{task}_{role}"],
                )
                for role in ("retrieval", "benchmark")
            ],
            group_level=group_level,
        )
        write_group_split_audit(group_report, group_audit_path)
        group_report.require_safe()
        group_audit_paths.append(group_audit_path.as_posix())

    knowledge = {
        name: list(
            NormalizedJsonlLoader(
                paths[name],
                dataset=manifest.dataset_name,
                collection="unused",
                manifest=manifest,
                expected_context_level=(
                    "src_fm" if manifest.metadata.get("task") == "testing" else None
                ),
            ).load_knowledge()
        )
        for name, manifest in manifests.items()
    }
    fingerprints = {
        name: [_fingerprint(document) for document in documents]
        for name, documents in knowledge.items()
    }
    for name, items in fingerprints.items():
        fingerprint_path = manifests[name].fingerprints_path
        if fingerprint_path:
            write_fingerprints(items, project_root / fingerprint_path)

    leakage_paths = []
    for task in ("testing", "refactoring"):
        indexed_name = f"{task}_retrieval"
        benchmark_name = f"{task}_benchmark"
        report = detect_leakage(
            fingerprints[indexed_name],
            fingerprints[benchmark_name],
            indexed_manifest_id=manifests[indexed_name].manifest_id,
            benchmark_manifest_id=manifests[benchmark_name].manifest_id,
        )
        report_path = audit_root / f"{task}_retrieval_vs_benchmark.json"
        write_leakage_report(report, report_path)
        report.require_safe()
        leakage_paths.append(report_path.as_posix())

    builder = ProductionCorpusBuilder(
        pipeline_version=config.ingestion.pipeline_version,
        literature_max_chars=config.ingestion.literature_max_chars,
        mixed_collection=config.collections.mixed,
        testing_collection=config.collections.tests,
        refactoring_collection=config.collections.refactor,
        literature_collection=config.collections.software_engineering_literature,
        pair_parser=SafeJavaSignatureParser(),
    )
    corpora = builder.build(
        refactoring=knowledge["refactoring_retrieval"],
        testing=knowledge["testing_retrieval"],
        literature=[],
    )
    equivalent = _require_equivalent_corpus(
        corpora[config.collections.mixed].documents,
        [
            corpora[config.collections.tests].documents,
            corpora[config.collections.refactor].documents,
        ],
    )

    vector_store = create_vector_store(config)
    if vector_store.manifest_store is None:
        raise RuntimeError("Production indexes require collection manifests.")
    lifecycle = CollectionIndexLifecycle(vector_store, vector_store.manifest_store)
    manifest_ids = {
        config.collections.tests: [manifests["testing_retrieval"].manifest_id],
        config.collections.refactor: [
            manifests["refactoring_retrieval"].manifest_id
        ],
        config.collections.mixed: sorted(
            [
                manifests["testing_retrieval"].manifest_id,
                manifests["refactoring_retrieval"].manifest_id,
            ]
        ),
    }
    collection_reports = []
    for collection_name in (
        config.collections.tests,
        config.collections.refactor,
        config.collections.mixed,
    ):
        documents = corpora[collection_name].documents
        manifest = create_collection_manifest(
            collection_name=collection_name,
            embedding_provider=vector_store.embedding_provider,
            embedding_normalized=config.embeddings.normalized,
            embedding_template_version="1",
            chunker_name="pair_aware_java",
            chunker_version=config.ingestion.pipeline_version,
            ingestion_pipeline_version=config.ingestion.pipeline_version,
            dataset_manifests=manifest_ids[collection_name],
        )
        if collection_name == config.collections.mixed:
            write_result, completed = lifecycle.rebuild_precomputed(
                manifest,
                documents,
                _read_specialized_embeddings(
                    vector_store,
                    [config.collections.tests, config.collections.refactor],
                ),
            )
            embedding_source = "reused_provider_vectors_from_disjoint_collections"
        else:
            existing = _compatible_existing_write(
                vector_store, manifest, documents
            )
            if existing is None:
                write_result, completed = lifecycle.rebuild(manifest, documents)
                embedding_source = "ollama_bge_m3"
            else:
                write_result, completed = existing
                embedding_source = "existing_compatible_ollama_bge_m3"
        collection_reports.append(
            ProductionCollectionReport(
                collection=collection_name,
                received=write_result.received,
                indexed=write_result.indexed,
                duplicates=write_result.duplicates,
                source_type_distribution=dict(
                    sorted(
                        Counter(
                            document.document_type.value for document in documents
                        ).items()
                    )
                ),
                dataset_manifest_ids=completed.dataset_manifests,
                collection_manifest_path=vector_store.manifest_store.path_for(
                    collection_name
                ).as_posix(),
                document_ids_digest=_document_ids_digest(documents),
                embedding_source=embedding_source,
            )
        )
    mixed_count = next(
        item.indexed
        for item in collection_reports
        if item.collection == config.collections.mixed
    )
    specialized_count = sum(
        item.indexed
        for item in collection_reports
        if item.collection != config.collections.mixed
    )
    if mixed_count != specialized_count:
        raise RuntimeError(
            "Indexed mixed and disjoint MultiRAG corpora are not equivalent: "
            f"mixed={mixed_count}, specialized={specialized_count}."
        )
    runtime = dict(vector_store.embedding_provider.runtime_metadata)
    return ProductionIndexReport(
        pipeline_version=config.ingestion.pipeline_version,
        embedding_provider=str(runtime.get("embedding_provider", "unknown")),
        embedding_model=vector_store.embedding_provider.model_identifier,
        embedding_revision=vector_store.embedding_provider.model_revision,
        embedding_model_digest=runtime.get("embedding_model_digest"),
        literature_status=(
            "not_indexed: no approved literature source is present in the repository"
        ),
        retrieval_documents=sum(
            len(knowledge[name])
            for name in ("testing_retrieval", "refactoring_retrieval")
        ),
        benchmark_documents=sum(
            len(knowledge[name])
            for name in ("testing_benchmark", "refactoring_benchmark")
        ),
        selection_exclusions=selection_exclusions,
        derived_manifest_paths=derived_manifest_paths,
        group_audit_paths=group_audit_paths,
        leakage_audit_paths=leakage_paths,
        equivalent_corpus=equivalent,
        collections=collection_reports,
    )


def _fingerprint(document: Any) -> SampleFingerprint:
    return SampleFingerprint(
        identity=document.identity.model_copy(update={"dataset": document.task}),
        input_code_hash=str(document.metadata["input_code_hash"]),
        focal_method_hash=str(document.metadata["focal_method_hash"]),
        full_document_hash=str(document.metadata["full_document_hash"]),
    )


def _require_equivalent_corpus(
    mixed: list[DocumentChunk], specialized: list[list[DocumentChunk]]
) -> bool:
    mixed_ids = {document.document_id for document in mixed}
    specialized_ids = {
        document.document_id
        for collection_documents in specialized
        for document in collection_documents
    }
    if mixed_ids != specialized_ids:
        raise RuntimeError(
            "Mixed and disjoint MultiRAG collections do not represent the same corpus."
        )
    return True


def _select_disjoint_records(
    retrieval: list[dict[str, Any]],
    benchmark: list[dict[str, Any]],
    *,
    group_level: GroupLevel,
) -> tuple[list[dict[str, Any]], int, int]:
    try:
        reserved = {record_group_key(record, group_level) for record in benchmark}
    except ValueError as exc:
        raise ValueError(
            f"Benchmark record lacks a required {group_level.value} identity."
        ) from exc
    identity_safe = [
        record
        for record in retrieval
        if record_group_key(record, group_level) not in reserved
    ]
    reserved_fingerprints = {
        key for record in benchmark for key in _record_fingerprint_keys(record)
    }
    selected = [
        record
        for record in identity_safe
        if _record_fingerprint_keys(record).isdisjoint(reserved_fingerprints)
    ]
    if not selected:
        raise ValueError(
            f"No retrieval records remain after {group_level.value} leakage filtering."
        )
    return (
        selected,
        len(retrieval) - len(identity_safe),
        len(identity_safe) - len(selected),
    )


def _record_fingerprint_keys(record: dict[str, Any]) -> set[tuple[str, str]]:
    input_code = str(record.get("input", "")).strip()
    full_document = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return {
        ("input_code_hash", java_code_hash(input_code)),
        ("focal_method_hash", java_code_hash(input_code)),
        ("full_document_hash", sha256_text(full_document)),
    }


def _document_ids_digest(documents: list[DocumentChunk]) -> str:
    payload = "\n".join(sorted(document.document_id for document in documents))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_specialized_embeddings(
    vector_store: Any, collection_names: list[str]
) -> dict[str, list[float]]:
    embeddings: dict[str, list[float]] = {}
    for collection_name in collection_names:
        collection = vector_store.client.get_collection(
            name=collection_name, embedding_function=None
        )
        result = collection.get(include=["embeddings"])
        ids = result.get("ids") or []
        vectors = result.get("embeddings")
        if vectors is None:
            raise RuntimeError(
                f"Collection {collection_name!r} did not return reusable embeddings."
            )
        for document_id, vector in zip(ids, vectors, strict=True):
            embeddings[str(document_id)] = [float(value) for value in vector]
    return embeddings


def _compatible_existing_write(
    vector_store: Any,
    expected_manifest: Any,
    documents: list[DocumentChunk],
) -> tuple[IndexWriteResult, Any] | None:
    try:
        actual = vector_store.manifest_store.require_compatible(
            expected_manifest.collection_name, expected_manifest
        )
        collection = vector_store.client.get_collection(
            name=expected_manifest.collection_name, embedding_function=None
        )
    except (IncompatibleCollectionError, ValueError):
        return None
    unique_count = len({document.content_hash for document in documents})
    if collection.count() != unique_count or actual.document_count != unique_count:
        return None
    return (
        IndexWriteResult(
            collection=expected_manifest.collection_name,
            received=len(documents),
            indexed=unique_count,
            duplicates=len(documents) - unique_count,
        ),
        actual,
    )
