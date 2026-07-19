from __future__ import annotations

import re
from typing import Iterable

from llm_ontology.retrieval.models import DocumentChunk, SourceDocument, make_document_chunk


class PassthroughChunker:
    """Keep an already meaningful dataset record as one retrieval unit."""

    def __init__(self, pipeline_version: str = "rag-v1") -> None:
        self.pipeline_version = pipeline_version

    def chunk(self, document: SourceDocument) -> Iterable[DocumentChunk]:
        yield make_document_chunk(document, pipeline_version=self.pipeline_version)


class StructuredTextChunker:
    """Split prose on Markdown headings and paragraph boundaries."""

    def __init__(self, max_chars: int = 1800, pipeline_version: str = "rag-v1") -> None:
        if max_chars < 200:
            raise ValueError("max_chars must be at least 200.")
        self.max_chars = max_chars
        self.pipeline_version = pipeline_version

    def chunk(self, document: SourceDocument) -> Iterable[DocumentChunk]:
        units = [unit.strip() for unit in re.split(r"\n\s*\n|(?=^#{1,6}\s)", document.content, flags=re.MULTILINE) if unit.strip()]
        chunks: list[str] = []
        current = ""
        for unit in units:
            if len(unit) > self.max_chars:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(_fixed_fallback(unit, self.max_chars))
            elif not current:
                current = unit
            elif len(current) + len(unit) + 2 <= self.max_chars:
                current = f"{current}\n\n{unit}"
            else:
                chunks.append(current)
                current = unit
        if current:
            chunks.append(current)

        for index, content in enumerate(chunks):
            heading = _first_heading(content)
            yield make_document_chunk(
                document,
                content=content,
                embedding_text=content,
                chunk_index=index,
                metadata={"section": heading} if heading else {},
                pipeline_version=self.pipeline_version,
            )


def _fixed_fallback(text: str, max_chars: int) -> list[str]:
    return [text[start : start + max_chars] for start in range(0, len(text), max_chars)]


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return ""
