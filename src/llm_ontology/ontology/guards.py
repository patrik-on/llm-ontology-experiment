"""Leak guard: an ontology block may only name things present in the supplied source."""
from __future__ import annotations

import re

from llm_ontology.ontology import views

IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
# Words the views themselves write; everything else must come from the source.
TEMPLATE_VOCABULARY = frozenset(IDENTIFIER.findall(
    "project ontology Focal method in Declared throws Throws when unconditionally line Decision points "
    "none if switch cases ternary loop for while do Boundary candidates try Null checks null Reads fields "
    "Calls Other public methods supplied source Target lines are inside of declarations type Fields "
    "Methods Names already declared read variables earlier assign used after write contain return yes no "
    "break continue Local Parameter Field initialised with at spans called Type constructors name "
    "referenced more Lines to Method"))


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
