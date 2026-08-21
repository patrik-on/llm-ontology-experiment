from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from llm_ontology.retrieval.config import RagConfig
from llm_ontology.vectorstore.manifest import CollectionManifest

if TYPE_CHECKING:
    from llm_ontology.experiments.smoke_models import SmokeExperimentConfig


class BaselineMismatchError(RuntimeError):
    """Raised before inference when the immutable baseline contract is not satisfied."""


def stable_sha256(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def collection_manifest_id(manifest: CollectionManifest) -> str:
    """Return a portable semantic manifest identity, excluding only its timestamp."""

    payload = manifest.model_dump(mode="json", exclude={"created_at"})
    payload["dataset_manifests"] = sorted(payload["dataset_manifests"])
    return stable_sha256(payload)


def collection_content_hash(manifest: CollectionManifest) -> str:
    """Identify the indexed corpus/chunking contract independently of build time."""

    return stable_sha256(
        {
            "collection_name": manifest.collection_name,
            "dataset_manifests": sorted(manifest.dataset_manifests),
            "document_count": manifest.document_count,
            "chunker_name": manifest.chunker_name,
            "chunker_version": manifest.chunker_version,
            "ingestion_pipeline_version": manifest.ingestion_pipeline_version,
            "embedding_template_version": manifest.embedding_template_version,
        }
    )


def baseline_contract_payload(config: SmokeExperimentConfig) -> dict[str, Any]:
    """Build the path- and timestamp-free payload protected by the fingerprint."""

    payload = {
        "contract_version": config.baseline_contract_version,
        "baseline_id": config.baseline_id,
        "matrix": {"modes": [mode.value for mode in config.modes]},
        "runtime": {
            "environment": config.runtime_environment,
            "ollama_base_url": config.ollama_base_url,
        },
        "generation": {
            "provider": config.generation_provider,
            "model": config.generation_model,
            "model_digest": config.generation_model_digest,
            "temperature": config.generation_temperature,
            "top_p": config.generation_top_p,
            "seed": config.random_seed,
            "max_output_tokens": config.generation_max_tokens,
            "context_window": config.total_context_tokens,
            "reserved_output_tokens": config.reserved_output_tokens,
            "safety_margin_tokens": config.safety_margin_tokens,
            "tokenizer_model": config.tokenizer_model,
            "tokenizer_revision": config.tokenizer_revision,
            "structured_output": {
                "enabled": config.structured_output_enabled,
                "format": config.structured_output_format,
                "schema_version": config.structured_output_schema_version,
                "repair_retry_limit": config.structured_retries,
            },
        },
        "embeddings": {
            "provider": config.embedding_provider,
            "model": config.embedding_model,
            "dimension": config.embedding_dimension,
            "model_digest": config.embedding_model_digest,
            "normalized": config.embedding_normalized,
        },
        "single_rag": {
            "collection": config.single_collection,
            "top_k": config.top_k,
            "retrieval_token_budget": config.retrieval_token_budget,
            "allowed_splits": sorted(config.allowed_splits),
        },
        "multi_rag": {
            "collections": list(config.multi_collections),
            "per_collection_top_k": config.per_collection_top_k,
            "global_top_k": config.top_k,
            "fusion": {"strategy": config.fusion_strategy, "k": config.rrf_k},
            "retrieval_token_budget": config.retrieval_token_budget,
            "allowed_splits": sorted(config.allowed_splits),
        },
        "prompts": {
            "prompt_template_version": config.prompt_template_version,
            "testing_prompt_template_sha256": config.testing_prompt_template_sha256,
            "refactoring_prompt_template_sha256": (config.refactoring_prompt_template_sha256),
        },
        "dataset": {
            "name": "handcrafted_smoke_v1",
            "manifest_id": config.smoke_dataset_manifest_id,
            "content_hash": config.smoke_dataset_content_hash,
        },
        "collections": {
            name: identity.model_dump(mode="json")
            for name, identity in sorted(config.collection_manifests.items())
        },
    }
    generation = payload["generation"]
    single_rag = payload["single_rag"]
    multi_rag = payload["multi_rag"]
    if config.ollama_num_ctx is not None:
        generation["ollama_num_ctx"] = config.ollama_num_ctx
    if config.fail_on_prompt_budget_exceeded is not None:
        generation["fail_on_prompt_budget_exceeded"] = config.fail_on_prompt_budget_exceeded
    if config.enforce_retrieval_token_budget is not None:
        single_rag["retrieval_budget_enforced"] = config.enforce_retrieval_token_budget
        multi_rag["retrieval_budget_enforced"] = config.enforce_retrieval_token_budget
    if config.task_filter_enabled is not None:
        single_rag["task_filter"] = "canonical_task" if config.task_filter_enabled else "disabled"
        multi_rag["task_filter"] = "canonical_task" if config.task_filter_enabled else "disabled"
    if config.max_retrieved_document_tokens is not None:
        single_rag["max_document_tokens"] = config.max_retrieved_document_tokens
        multi_rag["max_document_tokens"] = config.max_retrieved_document_tokens
    return payload


def compute_baseline_fingerprint(config: SmokeExperimentConfig) -> str:
    return stable_sha256(baseline_contract_payload(config))


def require_matching_fingerprint(config: SmokeExperimentConfig) -> None:
    actual = compute_baseline_fingerprint(config)
    if actual != config.baseline_fingerprint:
        raise BaselineMismatchError(
            "BASELINE_MISMATCH: baseline fingerprint differs from the effective "
            f"contract (expected {config.baseline_fingerprint}, computed {actual})."
        )


def effective_config_payload(
    config: SmokeExperimentConfig,
    rag: RagConfig,
) -> dict[str, Any]:
    """Return the fully resolved, portable snapshot written beside every run."""

    experiment = config.model_dump(
        mode="json",
        exclude={"retrieval_config"},
        exclude_none=True,
    )
    resolved_retrieval = rag.model_dump(mode="json")
    if resolved_retrieval["llm"].get("context_window_tokens") is None:
        resolved_retrieval["llm"].pop("context_window_tokens", None)
    resolved_retrieval["llm"]["max_tokens"] = config.generation_max_tokens
    resolved_retrieval["llm"]["seed"] = config.random_seed
    resolved_retrieval["retrieval"].update(
        {
            "top_k": config.top_k,
            "max_context_tokens": config.retrieval_token_budget,
            "allowed_splits": list(config.allowed_splits),
            "rrf_k": config.rrf_k,
            "per_collection_top_k": config.per_collection_top_k,
        }
    )
    return {
        "baseline_id": config.baseline_id,
        "baseline_fingerprint": config.baseline_fingerprint,
        "baseline_contract": baseline_contract_payload(config),
        "smoke_experiment": experiment,
        "resolved_retrieval_config": resolved_retrieval,
    }


def write_baseline_artifacts(
    config: SmokeExperimentConfig,
    rag: RagConfig,
    environment: dict[str, Any],
) -> None:
    effective = effective_config_payload(config, rag)
    try:
        import yaml

        effective_text = yaml.safe_dump(
            effective,
            allow_unicode=True,
            sort_keys=True,
        )
    except ImportError:  # pragma: no cover - PyYAML is a required dependency.
        effective_text = json.dumps(effective, ensure_ascii=False, indent=2, sort_keys=True)
        effective_text += "\n"
    environment_text = (
        json.dumps(
            environment,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    _write_immutable(config.output_dir / "effective_config.yaml", effective_text)
    _write_immutable(config.output_dir / "environment.json", environment_text)


def _write_immutable(path: Path, content: str) -> None:
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise BaselineMismatchError(
                "BASELINE_MISMATCH: immutable run artifact already exists with "
                f"different content: {path.as_posix()}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
