from __future__ import annotations

import importlib.metadata
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from llm_ontology.ingestion.documents import KnowledgeDocument, materialize_for_collection
from llm_ontology.ingestion.identity import CaseIdentity
from llm_ontology.ingestion.manifest import DatasetManifest
from llm_ontology.retrieval.models import DocumentType, SourceDocument, sha256_text


class PdfFailure(BaseModel):
    source_path: str
    reason: str


class PdfIngestionReport(BaseModel):
    requested_documents: int = 0
    loaded_documents: int = 0
    failed_documents: int = 0
    total_pages: int = 0
    extracted_pages: int = 0
    empty_or_damaged_pages: int = 0
    failures: list[PdfFailure] = Field(default_factory=list)


class PdfDocumentLoader:
    """Page-aware PDF literature loader with corpus-level header/footer cleanup."""

    loader_name = "pypdf"

    def __init__(
        self,
        paths: Iterable[str | Path] | None = None,
        *,
        dataset: str,
        collection: str,
        manifest: DatasetManifest,
        minimum_page_characters: int = 20,
    ) -> None:
        manifest_source = Path(manifest.source_path)
        self.paths = (
            [Path(path) for path in paths]
            if paths is not None
            else sorted(manifest_source.glob("*.pdf"))
        )
        self.dataset = dataset
        self.collection = collection
        self.manifest = manifest
        self.minimum_page_characters = minimum_page_characters
        self.loader_version = importlib.metadata.version("pypdf")
        self.report = PdfIngestionReport(requested_documents=len(self.paths))

    def load(self) -> Iterable[SourceDocument]:
        for document in self.load_knowledge():
            yield materialize_for_collection(document, self.collection)

    def load_knowledge(self) -> Iterable[KnowledgeDocument]:
        from pypdf import PdfReader

        self.manifest.require_indexable()
        _require_manifest_paths(self.paths, Path(self.manifest.source_path))
        report = PdfIngestionReport(requested_documents=len(self.paths))
        loaded: list[KnowledgeDocument] = []
        for path in self.paths:
            try:
                reader = PdfReader(path)
                raw_pages = [page.extract_text() or "" for page in reader.pages]
                headers, footers = _repeated_boundaries(raw_pages)
                report.total_pages += len(raw_pages)
                extracted_for_document = 0
                for page_index, raw_text in enumerate(raw_pages, 1):
                    cleaned = _clean_page(raw_text, headers, footers)
                    if not _page_is_usable(cleaned, self.minimum_page_characters):
                        report.empty_or_damaged_pages += 1
                        continue
                    extracted_for_document += 1
                    report.extracted_pages += 1
                    source_uri = f"{path.as_posix()}#page={page_index}"
                    loaded.append(
                        KnowledgeDocument(
                            content=cleaned,
                            document_type=DocumentType.LITERATURE,
                            source=path.name,
                            dataset=self.dataset,
                            source_split=self.manifest.source_split,
                            usage_role=self.manifest.usage_role.value,
                            task="software_engineering_literature",
                            source_uri=source_uri,
                            identity=CaseIdentity(
                                dataset=self.dataset,
                                case_id=f"{path.name}:page:{page_index}",
                                file_path=path.as_posix(),
                            ),
                            metadata={
                                "document_title": path.stem,
                                "source_path": path.as_posix(),
                                "page_start": page_index,
                                "page_end": page_index,
                                "section_title": "",
                                "content_hash": sha256_text(cleaned),
                                "loader_name": self.loader_name,
                                "loader_version": self.loader_version,
                            },
                        )
                    )
                if extracted_for_document:
                    report.loaded_documents += 1
                else:
                    report.failed_documents += 1
                    report.failures.append(
                        PdfFailure(
                            source_path=path.as_posix(),
                            reason="No extractable text; OCR preprocessing is required.",
                        )
                    )
            except Exception as exc:  # One corrupt source must not abort a corpus ingestion.
                report.failed_documents += 1
                report.failures.append(
                    PdfFailure(source_path=path.as_posix(), reason=f"{type(exc).__name__}: {exc}")
                )
        self.report = report
        yield from loaded


def _repeated_boundaries(pages: list[str]) -> tuple[set[str], set[str]]:
    non_empty_lines = [
        [line.strip() for line in page.splitlines() if line.strip()]
        for page in pages
    ]
    usable = [lines for lines in non_empty_lines if lines]
    if len(usable) < 2:
        return set(), set()
    threshold = max(2, math.ceil(len(usable) * 0.6))
    first = Counter(_boundary_key(lines[0]) for lines in usable)
    last = Counter(_boundary_key(lines[-1]) for lines in usable)
    headers = {value for value, count in first.items() if value and count >= threshold}
    footers = {value for value, count in last.items() if value and count >= threshold}
    return headers, footers


def _boundary_key(value: str) -> str:
    return re.sub(r"\d+", "#", " ".join(value.lower().split()))


def _clean_page(text: str, headers: set[str], footers: set[str]) -> str:
    lines = [line.strip() for line in text.replace(chr(13), "").split(chr(10))]
    non_empty_indexes = [index for index, line in enumerate(lines) if line]
    if non_empty_indexes:
        first = non_empty_indexes[0]
        last = non_empty_indexes[-1]
        if _boundary_key(lines[first]) in headers:
            lines[first] = ""
        if _boundary_key(lines[last]) in footers:
            lines[last] = ""
    return _join_wrapped_paragraphs(lines)


def _join_wrapped_paragraphs(lines: list[str]) -> str:
    paragraphs: list[str] = []
    current = ""
    for line in lines:
        if not line:
            if current:
                paragraphs.append(current.strip())
                current = ""
            continue
        if not current:
            current = line
        elif current.endswith("-") and line[:1].islower():
            current = current[:-1] + line
        else:
            current = current + " " + line
    if current:
        paragraphs.append(current.strip())
    return "\n\n".join(paragraphs).strip()


def _page_is_usable(text: str, minimum_characters: int) -> bool:
    meaningful = sum(character.isalnum() for character in text)
    return meaningful >= minimum_characters


def _require_manifest_paths(paths: list[Path], manifest_source: Path) -> None:
    approved_root = manifest_source.resolve()
    if manifest_source.is_file():
        unapproved = [path for path in paths if path.resolve() != approved_root]
    else:
        unapproved = [
            path
            for path in paths
            if path.resolve() != approved_root and approved_root not in path.resolve().parents
        ]
    if unapproved:
        rendered = ", ".join(path.as_posix() for path in unapproved)
        raise ValueError(
            f"PDF path is outside dataset manifest source_path {manifest_source}: {rendered}"
        )
