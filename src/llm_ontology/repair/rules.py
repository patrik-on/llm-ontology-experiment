"""Rule bases for the repair loop: handwritten SHACL (D1) plus template rules (D2).

A rule base is plain JSON, so a D2 version is one file with one hash. Handwritten shapes are
stored with their Turtle text; a rule the model proposes is a *template instance* built by
``proposal.py`` from a condition, an exception and a message chosen from the catalogue.
``render`` turns the base deterministically into one SHACL graph (Turtle), so free-form SHACL
written by the model never runs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from rdflib import Graph
from rdflib.namespace import SH

from llm_ontology.repair.java_facts import VOCABULARY

LOS = "https://w3id.org/llm-ontology/shapes#"
PREFIXES = """@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix lo:   <https://w3id.org/llm-ontology/project#> .
@prefix los:  <https://w3id.org/llm-ontology/shapes#> .
los: a owl:Ontology ;
  sh:declare [ sh:prefix "lo" ; sh:namespace "https://w3id.org/llm-ontology/project#"^^xsd:anyURI ] .
"""

# Closed list of conditions a proposal may use. Each names the facts it reads (all must be in
# java_facts.VOCABULARY), the parameters it accepts and the placeholders its message may use.
TEMPLATES: dict[str, dict[str, Any]] = {
    "new_parameter_used_only_in_role": {
        "task": "refactoring", "operation": "Parameterize Variable",
        "target": "lo:ParameterizeVariableRequest",
        "params": {"role": ["logging"]},
        "exceptions": ["none", "method_is_logging_helper"],
        "placeholders": ["m", "new", "role"],
        "facts": ["lo:newName", "lo:targetMethodAfter", "lo:display", "lo:hasParameter", "lo:name",
                  "lo:hasUse", "lo:resolvesKind", "lo:usageRole"],
        "describe": "the new parameter exists, but every use of it in the target method has the given role "
                    "(e.g. only logging), so the computation does not use it",
        "select": """SELECT $this ?m ?new ?role WHERE {{
        $this lo:newName ?new ; lo:targetMethodAfter ?ma .
        ?ma lo:display ?m ; lo:hasParameter ?p . ?p lo:name ?new .
        BIND ("{role}" AS ?role)
        FILTER NOT EXISTS {{ ?ma lo:hasUse ?u . ?u lo:name ?new ; lo:resolvesKind "parameter" ; lo:usageRole ?r .
                            FILTER (?r != ?role) }}
        {exception}
      }}""",
    },
    "old_local_still_declared": {
        "task": "refactoring", "operation": "Parameterize Variable",
        "target": "lo:ParameterizeVariableRequest", "params": {},
        "exceptions": ["none"], "placeholders": ["m", "old", "line"],
        "facts": ["lo:oldName", "lo:targetMethodAfter", "lo:display", "lo:declaresLocal", "lo:name", "lo:line"],
        "describe": "the target method still declares a local variable with the old name",
        "select": """SELECT $this ?m ?old ?line WHERE {{
        $this lo:oldName ?old ; lo:targetMethodAfter ?ma .
        ?ma lo:display ?m ; lo:declaresLocal ?l . ?l lo:name ?old ; lo:line ?line .
        {exception}
      }}""",
    },
    "mutated_argument_from_factory": {
        "task": "testing", "operation": "testing", "target": "lo:Argument",
        "params": {"mutability": ["Immutable", "FixedSize"]},
        "exceptions": ["none", "inside_expected_exception"],
        "placeholders": ["pos", "display", "factory", "method", "pname", "op"],
        "facts": ["lo:argumentOf", "lo:position", "lo:producedBy", "lo:factoryName", "lo:resultMutability",
                  "lo:resolvesTo", "lo:display", "lo:mutatesParameter", "lo:name", "lo:mutatedBy",
                  "lo:mutationOnSuccessPath"],
        "describe": "an argument from a collection factory of the given mutability is passed to a parameter "
                    "that the method mutates on its success path",
        "select": """SELECT $this ?pos ?display ?factory ?method ?pname ?op WHERE {{
        $this lo:argumentOf ?call ; lo:position ?pos ; lo:producedBy ?fac .
        ?fac lo:factoryName ?factory ; lo:resultMutability lo:{mutability} .
        ?call lo:resolvesTo ?e ; lo:display ?display .
        ?e lo:name ?method ; lo:mutatesParameter ?p .
        ?p lo:position ?pos ; lo:name ?pname ; lo:mutatedBy ?op ; lo:mutationOnSuccessPath true .
        {exception}
      }}""",
    },
}
RULE_DOCS = {
    "R1": "nothing outside the requested change is lost, modifiers (e.g. public) stay unchanged, "
          "and the target method exists in the output",
    "R2": "Parameterize Variable: the target method declares the new parameter, the old local "
          "variable is gone, and each paired use of the old variable refers to the new parameter",
    "T3": "an argument from an immutable or fixed-size collection factory is not passed to a parameter "
          "that the method mutates on its success path (unless the test expects the exception)",
}
EXCEPTION_DOCS = {
    "none": "no exception",
    "method_is_logging_helper": "skip when every statement of the target method is a logging call",
    "inside_expected_exception": "skip when the call is inside assertThrows (the exception is intended)",
}
EXCEPTIONS = {
    "none": "",
    "method_is_logging_helper": "FILTER NOT EXISTS { ?ma lo:isLoggingHelper true }",
    "inside_expected_exception": "FILTER NOT EXISTS { $this lo:inExpectedException true }",
}
MAX_MESSAGE = 300


class ProposalError(ValueError):
    """A proposal that cannot be turned into SHACL; ``code`` is the recorded reason."""
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(payload: Any) -> str:
    text = payload if isinstance(payload, str) else canonical(payload)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_d1(task: str, ttl_path: Path) -> dict:
    """D1: the handwritten shapes of one task, one rule per ID prefix (R1, R2, T3 ...)."""
    text = Path(ttl_path).read_text(encoding="utf-8")
    shapes = sorted(set(re.findall(r"^los:(\w+) a sh:NodeShape", text, flags=re.M)))
    rules: dict[str, list[str]] = {}
    for shape in shapes:
        rules.setdefault(shape.split("_", 1)[0], []).append(shape)
    return {"task": task, "facts_vocabulary": sorted(VOCABULARY), "handwritten_ttl": text,
            "handwritten_sha256": sha(text),
            "rules": [{"id": rid, "origin": "D1", "constraints": [{"kind": "handwritten", "shapes": s}]}
                      for rid, s in sorted(rules.items())]}


def base_hash(base: dict) -> str:
    return sha(base)


def _template_ttl(shape: str, constraint: dict) -> str:
    spec = TEMPLATES[constraint["template"]]
    select = spec["select"].format(exception=EXCEPTIONS[constraint["exception"]], **constraint["params"])
    message = (shape.rsplit("_t", 1)[0] + " " + constraint["message"]).replace("\\", "\\\\").replace('"', '\\"')
    return (f"los:{shape} a sh:NodeShape ;\n  sh:targetClass {spec['target']} ;\n  sh:sparql [\n"
            f"    a sh:SPARQLConstraint ; sh:prefixes los: ; sh:severity sh:Violation ;\n"
            f"    sh:message \"{message}\" ;\n    sh:select \"\"\"\n      {select}\"\"\" ;\n  ] .\n")


def shape_names(base: dict) -> dict[str, str]:
    """Shape local name -> rule ID."""
    out = {}
    for rule in base["rules"]:
        for k, c in enumerate(rule["constraints"]):
            if c["kind"] == "handwritten":
                out.update({s: rule["id"] for s in c["shapes"]})
            else:
                out[f"{rule['id']}_t{k}"] = rule["id"]
    return out


def render(base: dict) -> str:
    """The whole base as one Turtle document (handwritten text first, then template shapes)."""
    parts = [base["handwritten_ttl"] if base.get("handwritten_ttl") else PREFIXES]
    active = {s for r in base["rules"] for c in r["constraints"] if c["kind"] == "handwritten" for s in c["shapes"]}
    present = set(re.findall(r"^los:(\w+) a sh:NodeShape", parts[0], flags=re.M))
    if present - active:
        raise ValueError("Handwritten shapes not owned by a rule: " + ", ".join(sorted(present - active)))
    for rule in base["rules"]:
        for k, c in enumerate(rule["constraints"]):
            if c["kind"] == "template":
                parts.append(_template_ttl(f"{rule['id']}_t{k}", c))
    return "\n".join(parts)


def shapes_graph(base: dict) -> Graph:
    return Graph().parse(data=render(base), format="turtle")


def findings(data: Graph, base: dict, shapes: Graph | None = None) -> list[dict]:
    """Every SHACL result as {rule, shape, severity, message, focus}, sorted deterministically."""
    from pyshacl import validate

    shapes = shapes if shapes is not None else shapes_graph(base)
    _, report, _ = validate(data, shacl_graph=shapes, advanced=True, allow_warnings=True)
    names = shape_names(base)
    owner = {ps: ns for ns, ps in shapes.subject_objects(SH.property)}  # property shape -> node shape
    rows = []
    for result in report.subjects(SH.resultSeverity, None):
        node = report.value(result, SH.sourceShape)
        source = str(owner.get(node, node) or "")
        shape = source[len(LOS):] if source.startswith(LOS) else source
        rows.append({"rule": names.get(shape, "?"), "shape": shape,
                     "severity": str(report.value(result, SH.resultSeverity)).rsplit("#", 1)[-1],
                     "message": str(report.value(result, SH.resultMessage) or ""),
                     "focus": str(report.value(result, SH.focusNode) or "")})
    return sorted(rows, key=lambda r: (r["rule"], r["shape"], r["message"], r["focus"]))


def violations(rows: list[dict], rule: str | None = None) -> list[dict]:
    return [r for r in rows if r["severity"] == "Violation" and (rule is None or r["rule"] == rule)]
