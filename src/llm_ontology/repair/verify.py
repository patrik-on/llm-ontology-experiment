"""Independent check of a D2 rule candidate on labelled development examples.

The author (the model) never sees these examples or their labels. Labels come from the final
evaluator (``label_source = "final_evaluator"``) or from a manual check (``"manual"``); the
methodology must say that labels derived from the final evaluator carry gold information
into the D2 base. Examples of the task that triggered the proposal (same ``group``) are never
used, so a rule must generalise to another task to be accepted.

Decisions: ``accepted``, ``rejected`` (with a reason), ``pending`` (not enough examples),
``deferred`` (needs facts that are not extracted).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from time import perf_counter
from typing import Callable

from rdflib import Graph

from llm_ontology.repair import rules as R


@dataclass
class Example:
    id: str
    group: str
    task: str
    operation: str
    defective: bool
    label_source: str
    build: Callable[[], Graph] = field(repr=False)
    _graph: Graph | None = field(default=None, repr=False)

    def graph(self) -> Graph:
        if self._graph is None:
            self._graph = self.build()
        return self._graph


def load_pool(path: Path) -> list[Example]:
    """Pool file: JSON list. Refactoring entries carry before/after/request/target_start;
    testing entries carry ``facts_ttl`` (path relative to the pool file)."""
    from llm_ontology.repair.java_facts import refactoring_graph

    path = Path(path)
    out = []
    for row in json.loads(path.read_text(encoding="utf-8")):
        if row["task"] == "refactoring":
            def build(row=row):
                return refactoring_graph(row["before"], row["after"], row["request"], int(row["target_start"]))
        else:
            def build(row=row):
                return Graph().parse(path.parent / row["facts_ttl"])
        out.append(Example(row["id"], row["group"], row["task"], row["operation"], bool(row["defective"]),
                           row["label_source"], build))
    return out


def _flags(graph: Graph, base: dict, shapes: Graph, rule: str | None) -> bool:
    return bool(R.violations(R.findings(graph, base, shapes), rule))


def verify(*, decision: str, candidate: dict, current: dict, rule: str, operation: str,
           trigger: Graph | None, trigger_group: str, pool: list[Example]) -> dict:
    """Run every check and return {decision, reason, checks}. Never raises on bad candidates."""
    start = perf_counter()
    checks: dict = {}
    try:
        cand_shapes = R.shapes_graph(candidate)
        cur_shapes = R.shapes_graph(current)
        if trigger is not None:
            R.findings(trigger, candidate, cand_shapes)
        checks["loads"] = True
    except Exception as exc:  # malformed Turtle or SPARQL: reject, record why
        return {"decision": "rejected", "reason": "does_not_load", "checks": {"loads": False, "error": str(exc)},
                "seconds": perf_counter() - start}
    examples = [e for e in pool if e.task == candidate["task"] and e.operation == operation
                and e.group != trigger_group]
    positives = [e for e in examples if e.defective]
    negatives = [e for e in examples if not e.defective]
    checks.update(heldout_positives=len(positives), heldout_negatives=len(negatives),
                  heldout_groups=sorted({e.group for e in examples}))
    if trigger is not None:
        checks["trigger_flagged_before"] = _flags(trigger, current, cur_shapes, rule if decision == "modify" else None)
        checks["trigger_flagged_after"] = _flags(trigger, candidate, cand_shapes, rule)
    if not positives or not negatives:
        return {"decision": "pending", "reason": "missing_examples", "checks": checks, "seconds": perf_counter() - start}
    cand = {e.id: _flags(e.graph(), candidate, cand_shapes, rule) for e in examples}
    base_any = {e.id: _flags(e.graph(), current, cur_shapes, None) for e in examples}
    prev_rule = {e.id: _flags(e.graph(), current, cur_shapes, rule) for e in examples} if decision == "modify" else {}
    new_false = [e.id for e in negatives if cand[e.id] and not (prev_rule.get(e.id) or False)]
    caught = [e.id for e in positives if cand[e.id]]
    added = [i for i in caught if not base_any[i]]
    regressions = [e.id for e in positives if prev_rule.get(e.id) and not cand[e.id]]
    checks.update(caught=caught, added_coverage=added, new_false_positives=new_false, regressions=regressions)
    if trigger is not None and not checks["trigger_flagged_after"]:
        reason = "does_not_flag_trigger"
    elif new_false:
        reason = "flags_correct_example"
    elif regressions:
        reason = "regression"
    elif decision == "modify" and checks.get("trigger_flagged_before"):
        reason = "trigger_already_flagged"
    elif not caught:
        reason = "no_heldout_catch"
    elif not added:
        reason = "duplicate_no_added_coverage"
    else:
        reason = ""
    return {"decision": "rejected" if reason else "accepted", "reason": reason, "checks": checks,
            "seconds": perf_counter() - start}
