"""Leak guard: an ontology block may only name things present in the supplied source."""
from __future__ import annotations

import re

from llm_ontology.ontology import views

IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def _template_vocabulary() -> frozenset[str]:
    """Words the generator itself writes: identifiers in non-docstring string literals of the
    view and extractor modules (SPARQL queries excluded)."""
    import ast
    from pathlib import Path

    from llm_ontology.ontology import extract

    words = set()
    for module in (views, extract):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
                    and not node.value.lstrip().startswith(("SELECT ", "PREFIX "))):
                words.update(IDENTIFIER.findall(node.value))
    return frozenset(words)


TEMPLATE_VOCABULARY = _template_vocabulary()


def ungrounded_names(block: str, source: str) -> list[str]:
    """Identifiers in ``block`` that occur neither in ``source`` nor in the view templates."""
    present = set(IDENTIFIER.findall(source))
    body = block.removeprefix(views.OPEN).removesuffix(views.CLOSE)
    return sorted({w for w in IDENTIFIER.findall(body)
                   if w not in present and w not in TEMPLATE_VOCABULARY and not w.isdigit()})


def assert_grounded(block: str, source: str, *, forbidden: tuple[str, ...] = ()) -> None:
    """Raise if the block names anything not in the source or contains a forbidden (gold) string."""
    extra = ungrounded_names(block, source)
    if extra:
        raise ValueError("Ontology block names things absent from the supplied source: " + ", ".join(extra))
    for text in forbidden:
        if text and text.strip() and text.strip() in block:
            raise ValueError("Ontology block contains forbidden (gold) text")
