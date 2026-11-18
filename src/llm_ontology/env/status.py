"""Read-only status of the shared WSL experiment runtime (Ollama, models, Chroma)."""

from __future__ import annotations

import importlib.util
import os
import platform
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from llm_ontology.core.paths import resolve_path
from llm_ontology.retrieval.config import RagConfig
from llm_ontology.retrieval.factory import create_embedding_provider, create_llm_provider
from llm_ontology.vectorstore.chroma import create_chroma_client
from llm_ontology.vectorstore.manifest import CollectionManifestStore, IncompatibleCollectionError


class CollectionStatus(BaseModel):
    name: str
    document_count: int | str = "N/A"
    embedding_provider: str = "N/A"
    embedding_model: str = "N/A"
    embedding_revision: str = "N/A"
    embedding_model_digest: str = "N/A"
    embedding_dimension: int | str = "N/A"
    ollama_runtime: str = "N/A"
    chunker_version: str = "N/A"
    manifest_status: str = "missing"


class EnvironmentStatus(BaseModel):
    status: str = "NOT_READY"
    runtime_os: str = "N/A"
    runtime_environment: str = "N/A"
    ollama_status: str
    ollama_base_url: str = "N/A"
    configured_model: str
    model_available: bool
    model_digest: str = "N/A"
    chroma_path: str
    chroma_status: str
    embedding_provider: str = "N/A"
    embedding_model: str
    embedding_revision: str
    embedding_model_digest: str = "N/A"
    embedding_dimension: int | str = "N/A"
    embedding_base_url: str = "N/A"
    embedding_status: str = "N/A"
    generation_provider: str = "N/A"
    generation_model: str = "N/A"
    generation_model_digest: str = "N/A"
    generation_status: str = "N/A"
    python_version: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    collections: list[CollectionStatus] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class EnvironmentStatusService:
    def __init__(
        self,
        rag_config: RagConfig,
        *,
        timeout_seconds: float = 3.0,
        embedding_provider_factory: Callable[[Any], Any] = create_embedding_provider,
        llm_provider_factory: Callable[[Any], Any] = create_llm_provider,
        chroma_client_factory: Callable[[str | Path | None], Any] = create_chroma_client,
        runtime_probe: Callable[[], tuple[str, bool]] | None = None,
        dependency_probe: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.rag_config = rag_config
        self.timeout_seconds = timeout_seconds
        self.embedding_provider_factory = embedding_provider_factory
        self.llm_provider_factory = llm_provider_factory
        self.chroma_client_factory = chroma_client_factory
        self.runtime_probe = runtime_probe or _runtime_identity
        self.dependency_probe = dependency_probe or _dependency_status

    def inspect(self) -> EnvironmentStatus:
        errors: list[str] = []
        runtime_os, is_wsl = self.runtime_probe()
        runtime_environment = self.rag_config.runtime.environment
        if runtime_environment == "wsl" and not is_wsl:
            errors.append(
                "WSL-only runtime required: run this command inside Linux/WSL; "
                "Windows fallback is disabled."
            )
        model_available = False
        model_digest = "N/A"
        generation_status = "Unavailable"
        generation_provider = self.rag_config.llm.provider
        generation_model = self.rag_config.llm.model
        try:
            llm_settings = self.rag_config.llm.model_copy(
                update={"timeout_seconds": self.timeout_seconds}
            )
            provider = self.llm_provider_factory(llm_settings)
            generation_provider = str(
                getattr(provider, "provider_name", self.rag_config.llm.provider)
            )
            resolver = getattr(provider, "resolve_model_digest", None)
            if callable(resolver):
                model_digest = str(resolver())
            else:
                model_digest = str(getattr(provider, "model_version", "N/A"))
            model_available = True
            generation_status = "Ready"
        except Exception as exc:  # noqa: BLE001 - status probes are best-effort.
            errors.append(_friendly_error(exc))

        embedding_settings = self.rag_config.embeddings
        embedding_provider_name = embedding_settings.provider
        embedding_model = embedding_settings.model
        embedding_revision = embedding_settings.revision or "N/A"
        embedding_model_digest = embedding_settings.revision or "N/A"
        embedding_dimension: int | str = embedding_settings.dimension or "N/A"
        embedding_base_url = (
            embedding_settings.base_url
            if embedding_provider_name == "ollama"
            else "N/A"
        )
        embedding_status = "configured"
        if embedding_provider_name == "ollama":
            try:
                runtime_settings = embedding_settings.model_copy(
                    update={"timeout_seconds": self.timeout_seconds}
                )
                embedding_provider = self.embedding_provider_factory(runtime_settings)
                runtime = dict(embedding_provider.runtime_metadata)
                embedding_model = str(runtime["embedding_model"])
                embedding_model_digest = str(runtime["embedding_model_digest"])
                embedding_revision = embedding_model_digest
                embedding_dimension = int(runtime["embedding_dimension"])
                embedding_base_url = str(runtime["embedding_base_url"])
                embedding_status = "Ready"
            except Exception as exc:  # noqa: BLE001 - status probes are best-effort.
                embedding_status = "Unavailable"
                errors.append(_friendly_error(exc))

        chroma_path = resolve_path(self.rag_config.vector_store.persist_path)
        collections: list[CollectionStatus] = []
        chroma_status = "missing"
        if chroma_path.exists():
            try:
                client = self.chroma_client_factory(chroma_path)
                manifest_store = CollectionManifestStore(chroma_path)
                names = sorted(
                    getattr(collection, "name", str(collection))
                    for collection in client.list_collections()
                )
                for name in names:
                    collection = client.get_collection(name=name)
                    try:
                        manifest = manifest_store.read(name)
                    except IncompatibleCollectionError:
                        manifest = None
                    collections.append(
                        CollectionStatus(
                            name=name,
                            document_count=collection.count(),
                            embedding_provider=(
                                manifest.embedding_provider if manifest else "N/A"
                            ),
                            embedding_model=(
                                manifest.embedding_model if manifest else "N/A"
                            ),
                            embedding_revision=(
                                manifest.embedding_revision or "N/A"
                                if manifest
                                else "N/A"
                            ),
                            embedding_model_digest=(
                                manifest.embedding_model_digest or "N/A"
                                if manifest
                                else "N/A"
                            ),
                            embedding_dimension=(
                                manifest.embedding_dimension if manifest else "N/A"
                            ),
                            ollama_runtime=(
                                manifest.ollama_runtime if manifest else "N/A"
                            ),
                            chunker_version=(
                                manifest.chunker_version if manifest else "N/A"
                            ),
                            manifest_status="valid" if manifest else "missing",
                        )
                    )
                chroma_status = "available"
            except Exception as exc:  # noqa: BLE001 - status probes are best-effort.
                chroma_status = "error"
                errors.append(_friendly_error(exc))
        elif chroma_path.parent.exists():
            chroma_status = "not_initialized"

        dependencies = self.dependency_probe()
        missing_dependencies = [
            name for name, status in dependencies.items() if status != "available"
        ]
        if runtime_environment == "wsl" and missing_dependencies:
            errors.append(
                "Missing base dependencies: " + ", ".join(missing_dependencies)
            )

        uses_ollama = {
            self.rag_config.embeddings.provider,
            self.rag_config.llm.provider,
        } == {"ollama"}
        ollama_status = (
            "Ready"
            if uses_ollama
            and embedding_status == "Ready"
            and generation_status == "Ready"
            else "Unavailable" if "ollama" in {
                self.rag_config.embeddings.provider,
                self.rag_config.llm.provider,
            } else "Not configured"
        )
        chroma_available = chroma_status in {"available", "not_initialized"}
        strict_ready = (
            is_wsl
            and uses_ollama
            and ollama_status == "Ready"
            and chroma_available
            and not missing_dependencies
            and not errors
        )
        status = "READY" if strict_ready else "NOT_READY"

        return EnvironmentStatus(
            status=status,
            runtime_os=runtime_os,
            runtime_environment=runtime_environment,
            ollama_status=ollama_status,
            ollama_base_url=self.rag_config.runtime.ollama_base_url,
            configured_model=self.rag_config.llm.model,
            model_available=model_available,
            model_digest=model_digest,
            chroma_path=str(chroma_path),
            chroma_status=chroma_status,
            embedding_provider=embedding_provider_name,
            embedding_model=embedding_model,
            embedding_revision=embedding_revision,
            embedding_model_digest=embedding_model_digest,
            embedding_dimension=embedding_dimension,
            embedding_base_url=embedding_base_url,
            embedding_status=embedding_status,
            generation_provider=generation_provider,
            generation_model=generation_model,
            generation_model_digest=model_digest,
            generation_status=generation_status,
            python_version=platform.python_version(),
            dependencies=dependencies,
            collections=collections,
            errors=errors,
        )


def _runtime_identity() -> tuple[str, bool]:
    system = platform.system()
    release = platform.release()
    version = platform.version()
    is_linux = system == "Linux"
    is_wsl = is_linux and (
        bool(os.environ.get("WSL_DISTRO_NAME"))
        or "microsoft" in release.lower()
        or "microsoft" in version.lower()
    )
    label = f"{system} {release}"
    return (f"WSL/Linux ({label})" if is_wsl else label, is_wsl)


def _dependency_status() -> dict[str, str]:
    modules = {
        "pydantic": "pydantic",
        "pyyaml": "yaml",
        "chromadb": "chromadb",
    }
    return {
        name: "available" if importlib.util.find_spec(module) is not None else "missing"
        for name, module in modules.items()
    }


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, ValidationError):
        return "Invalid input: " + "; ".join(
            error["msg"] for error in exc.errors()
        )
    if isinstance(exc, IncompatibleCollectionError):
        return "Stale or missing collection manifest: " + text
    if isinstance(exc, NotImplementedError):
        return text
    if "not reachable" in lowered or "ollama server" in lowered:
        return "Ollama server unavailable. Start Ollama and refresh Environment status."
    if "not installed" in lowered and "ollama" in lowered:
        return "Configured Ollama model is not installed: " + text
    if "collection" in lowered and (
        "does not exist" in lowered or "not found" in lowered or "missing" in lowered
    ):
        return "Chroma collection is missing: " + text
    if "chroma database" in lowered and "missing" in lowered:
        return text
    if "chromadb is not installed" in lowered:
        return "ChromaDB is unavailable. Install the project rag dependencies."
    if "fixed prompt exceeds" in lowered or "context window" in lowered:
        return "Prompt is too large for the configured token budget."
    if "structured output" in lowered:
        return "Structured output failed: " + text
    if "java input" in lowered:
        return text
    if "configuration" in lowered or "config" in lowered:
        return "Configuration error: " + text
    return text or exc.__class__.__name__
