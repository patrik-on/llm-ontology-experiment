"""Project ontology for the ``onto_project`` and ``ft_onto`` arms.

A per-case RDF graph built from the supplied Java source only (``graph``), queried with
SPARQL and verbalised into a short ``<project-ontology>`` block (``views``). ``guards``
checks that a block names nothing outside the supplied source and no gold text.
"""
from __future__ import annotations

import hashlib
from typing import Any

from llm_ontology.ontology.graph import SCHEMA_VERSION, build_graph, graph_ntriples, schema_sha256
from llm_ontology.ontology.guards import assert_grounded, ungrounded_names
from llm_ontology.ontology.views import refactoring_view, testing_view

__all__ = ["ONTOLOGY_HEADER", "SCHEMA_VERSION", "with_ontology", "assert_grounded", "build_graph", "graph_ntriples", "refactoring_context",
           "refactoring_view", "schema_sha256", "testing_context", "testing_view", "ungrounded_names"]


ONTOLOGY_HEADER = ("Project ontology: facts extracted automatically from the supplied code only. "
                   "They describe that code; the task and output contract above take precedence.")


def with_ontology(instruction: str, block: str) -> str:
    """The one place a block enters a prompt: after the instruction, before ``### Input``.
    Used by the FT dataset builder and by every ontology arm, so training and evaluation
    prompts stay byte-identical."""
    return instruction + "\n" + ONTOLOGY_HEADER + "\n" + block


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _identity(block: str, source: str, graph) -> dict[str, str]:
    return {"schema_version": SCHEMA_VERSION, "schema_sha256": schema_sha256(),
            "source_sha256": _sha(source), "graph_sha256": _sha(graph_ntriples(graph)),
            "block_sha256": _sha(block)}


def testing_context(case: Any, *, forbidden: tuple[str, ...] = ()) -> tuple[str, dict[str, str]]:
    """Ontology block and identity for a testing ``ExperimentCase`` (input = production class).

    ``forbidden`` holds gold texts (reference tests) that must not appear in the block.
    """
    ident = case.structured_identity
    source = case.input_text
    block = testing_view(source, ident["method_name"], ident.get("class_name", "").split(".")[-1])
    assert_grounded(block, source, forbidden=forbidden)
    return block, _identity(block, source, build_graph(source))


def refactoring_context(case: dict[str, Any], *, forbidden: tuple[str, ...] = ()) -> tuple[str, dict[str, str]]:
    """Ontology block and identity for a refactoring cohort case.

    Uses only public inputs every arm receives: ``before``, ``operation``, ``target`` lines and the
    ``request`` text. Reference outputs and evaluator data are never read.
    """
    source, target = case["before"], case["target"]
    block = refactoring_view(source, case["operation"], int(target["start"]), int(target["end"]),
                             case.get("request") or "")
    assert_grounded(block, source, forbidden=forbidden)
    return block, _identity(block, source, build_graph(source, block=(int(target["start"]), int(target["end"]))))
