from __future__ import annotations

import re
from dataclasses import dataclass

from llm_ontology.retrieval.models import RetrievalHit


_WORD_PATTERN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SIGNATURE_PATTERN = re.compile(
    r"\b(?P<return>boolean|byte|short|int|long|float|double|char|void|String|"
    r"[A-Za-z_$][A-Za-z0-9_$<>.?\[\]]*)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\((?P<parameters>[^)]*)\)"
)
_STOPWORDS = {
    "class",
    "code",
    "corresponding",
    "final",
    "generation",
    "java",
    "original",
    "private",
    "production",
    "protected",
    "public",
    "refactored",
    "return",
    "static",
    "task",
    "test",
    "this",
    "void",
}
_CONTROL_TOKENS = ("if", "else", "for", "while", "switch", "try", "catch", "throw")
_OPERATORS = ("==", "!=", ">=", "<=", "&&", "||", "+", "-", "*", "/", "%")


@dataclass(frozen=True, slots=True)
class _CodeShape:
    return_category: str
    method_name: str
    parameter_count: int
    controls: frozenset[str]
    operators: frozenset[str]


class CodeAwareReranker:
    """Deterministic input-side reranker for a small dense-retrieval candidate pool."""

    strategy_name = "code_aware_v1"

    def rerank(self, query: str, documents: list[RetrievalHit]) -> list[RetrievalHit]:
        query_tokens = _semantic_tokens(query)
        query_shape = _code_shape(_query_code(query))
        ranked = []
        for document in documents:
            evidence_input = _evidence_input(document.content)
            lexical = _lexical_similarity(query_tokens, _semantic_tokens(evidence_input))
            evidence_shape = _code_shape(evidence_input)
            shape = _shape_similarity(query_shape, evidence_shape)
            vector = max(0.0, min(1.0, float(document.score)))
            method_bonus = _method_name_bonus(query_shape, evidence_shape)
            score = min(
                1.0,
                0.40 * vector + 0.20 * lexical + 0.20 * shape + method_bonus,
            )
            ranked.append(document.model_copy(update={"reranking_score": score}))
        ranked.sort(
            key=lambda item: (
                -(item.reranking_score or 0.0),
                -item.score,
                item.document_id,
            )
        )
        return [
            item.model_copy(update={"final_rank": rank})
            for rank, item in enumerate(ranked, start=1)
        ]


def query_method_name(query: str) -> str:
    """Return the focal Java method encoded in a raw or task-aware query."""

    shape = _code_shape(_query_code(query))
    return shape.method_name if shape is not None else ""


def _semantic_tokens(text: str) -> set[str]:
    values: set[str] = set()
    for raw in _WORD_PATTERN.findall(text):
        for part in _CAMEL_BOUNDARY.sub(" ", raw).replace("_", " ").split():
            normalized = part.lower()
            if len(normalized) > 1 and normalized not in _STOPWORDS:
                values.add(normalized)
    return values


def _lexical_similarity(query: set[str], document: set[str]) -> float:
    if not query or not document:
        return 0.0
    overlap = len(query & document)
    containment = overlap / len(query)
    jaccard = overlap / len(query | document)
    return 0.7 * containment + 0.3 * jaccard


def _query_code(text: str) -> str:
    for marker in ("Production Java code:\n", "Original Java code:\n"):
        if marker in text:
            return text.split(marker, 1)[1]
    return text


def _evidence_input(text: str) -> str:
    for marker in ("\n\nCorresponding test code:\n", "\n\nRefactored Java code:\n"):
        if marker in text:
            return text.split(marker, 1)[0]
    return text


def _code_shape(text: str) -> _CodeShape | None:
    match = _SIGNATURE_PATTERN.search(text)
    if match is None:
        return None
    parameters = match.group("parameters").strip()
    parameter_count = _parameter_count(parameters)
    return _CodeShape(
        return_category=_return_category(match.group("return")),
        method_name=match.group("name").lower(),
        parameter_count=parameter_count,
        controls=frozenset(token for token in _CONTROL_TOKENS if re.search(rf"\b{token}\b", text)),
        operators=frozenset(operator for operator in _OPERATORS if operator in text),
    )


def _parameter_count(parameters: str) -> int:
    """Count Java parameters without treating generic type commas as separators."""

    if not parameters:
        return 0
    depth = 0
    count = 1
    for character in parameters:
        if character in "<([":
            depth += 1
        elif character in ">)]":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            count += 1
    return count


def _return_category(value: str) -> str:
    if value == "boolean":
        return "boolean"
    if value in {"byte", "short", "int", "long", "float", "double"}:
        return "numeric"
    if value in {"String", "char"}:
        return "text"
    if value == "void":
        return "void"
    return "object"


def _shape_similarity(left: _CodeShape | None, right: _CodeShape | None) -> float:
    if left is None or right is None:
        return 0.0
    return (
        0.4 * (left.return_category == right.return_category)
        + 0.3 * (1.0 / (1.0 + abs(left.parameter_count - right.parameter_count)))
        + 0.15 * _set_similarity(left.controls, right.controls)
        + 0.15 * _set_similarity(left.operators, right.operators)
    )


def _set_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _method_name_bonus(left: _CodeShape | None, right: _CodeShape | None) -> float:
    if left is None or right is None or left.method_name != right.method_name:
        return 0.0
    return 0.20
