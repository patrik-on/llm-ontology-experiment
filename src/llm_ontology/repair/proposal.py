"""The rule template the D2 analysis fills in, generated from one source.

``catalogue(base)`` lists what the validator accepts for the active base: conditions (template
plus fixed parameters), the relations (facts) each condition reads, exceptions, operations and
the IDs of the active rules. The prompt text (``prompt_section``) and the JSON schema
(``schema``) are both built from it, so the model sees exactly the values ``to_constraint``
accepts. ``required_facts`` and the SHACL shape are derived in code, never written by the model.

Three answers: ``add`` (evidence, applies_when, must_hold, except_when, message), ``revise`` (the
same plus target_rule from the active IDs) and ``none`` (reason; optional missing_facts, which
defers the case when a needed concept is not extracted). The evidence snippet must occur in
the current answer; a logging condition must quote a logging call.
"""
from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import BaseModel, Field

from llm_ontology.repair import rules as R
from llm_ontology.repair.java_facts import LOG_METHODS

PROMPT_VERSION = "d2-rule-template-v2"

FACT_DOCS = {
    "lo:newName": "the new name given in the request",
    "lo:oldName": "the old variable name given in the request",
    "lo:targetMethodAfter": "the method the request names, as it appears in your output",
    "lo:display": "readable name of a declaration",
    "lo:hasParameter": "a parameter of a method",
    "lo:name": "the name of a parameter, variable or use",
    "lo:hasUse": "one use of a variable name inside the method body",
    "lo:resolvesKind": "what a use refers to: parameter, local, field, literal or unknown",
    "lo:usageRole": "logging if the use is inside a logging call (log.debug, System.out.println ...), "
                    "otherwise computation",
    "lo:declaresLocal": "a local variable declared in the method",
    "lo:line": "line number in your output",
    "lo:isLoggingHelper": "true if every statement of the method is a logging call",
    "lo:argumentOf": "the call an argument belongs to",
    "lo:position": "argument or parameter position (0-based)",
    "lo:producedBy": "the collection factory an argument comes from (List.of, Arrays.asList, new ArrayList ...)",
    "lo:factoryName": "the name of that factory",
    "lo:resultMutability": "Mutable, FixedSize or Immutable result of the factory",
    "lo:resolvesTo": "the method a call resolves to",
    "lo:mutatesParameter": "a parameter that the method changes (add, put, remove, clear ...)",
    "lo:mutatedBy": "the operation that changes the parameter",
    "lo:mutationOnSuccessPath": "true if the change happens whenever the method succeeds",
    "lo:inExpectedException": "true if the call is inside assertThrows",
}
EXCEPTION_FACTS = {"method_is_logging_helper": "lo:isLoggingHelper", "inside_expected_exception": "lo:inExpectedException"}
LOGGING_CALL = re.compile(r"\b(" + "|".join(sorted(LOG_METHODS)) + r")\s*\(")


def conditions(task: str) -> dict[str, dict]:
    """Template x fixed parameter values -> one named condition each."""
    out = {}
    for name, spec in R.TEMPLATES.items():
        if spec["task"] != task:
            continue
        if not spec["params"]:
            out[name] = {"template": name, "params": {}}
            continue
        (key, values), = spec["params"].items()  # every template has at most one parameter
        for value in values:
            out[f"{name}:{value}"] = {"template": name, "params": {key: value}}
    for cid, cond in out.items():
        spec = R.TEMPLATES[cond["template"]]
        cond.update(operation=spec["operation"], facts=list(spec["facts"]), exceptions=list(spec["exceptions"]),
                    placeholders=list(spec["placeholders"]),
                    describe=spec["describe"] + (f" ({', '.join(f'{k}={v}' for k, v in cond['params'].items())})"
                                                 if cond["params"] else ""))
    return out


def rule_ids(base: dict) -> dict[str, str]:
    out = {}
    for rule in base["rules"]:
        parts = []
        for c in rule["constraints"]:
            if c["kind"] == "handwritten":
                parts.append(R.RULE_DOCS.get(rule["id"], "handwritten rule"))
            else:
                parts.append(f"added condition {c['must_hold']} (exception {c['exception']})")
        out[rule["id"]] = "; ".join(parts)
    return out


def catalogue(base: dict) -> dict:
    conds = conditions(base["task"])
    exceptions = sorted({x for c in conds.values() for x in c["exceptions"]})
    facts = sorted({f for c in conds.values() for f in c["facts"]} | {EXCEPTION_FACTS[e] for e in exceptions
                                                                        if e in EXCEPTION_FACTS})
    return {"version": PROMPT_VERSION, "task": base["task"], "conditions": conds,
            "operations": sorted({c["operation"] for c in conds.values()}),
            "exceptions": {e: R.EXCEPTION_DOCS[e] for e in exceptions},
            "relations": {f: FACT_DOCS[f] for f in facts if f in FACT_DOCS}, "rules": rule_ids(base)}


def schema(base: dict) -> dict:
    """JSON schema of ``rule_proposal`` with exactly the enumerations of the catalogue."""
    cat = catalogue(base)
    evidence = {"type": "object", "properties": {"line": {"type": "integer"}, "snippet": {"type": "string"}},
                "required": ["snippet"], "additionalProperties": False}
    common = {"evidence": evidence, "applies_when": {"type": "string", "enum": cat["operations"]},
              "must_hold": {"type": "string", "enum": sorted(cat["conditions"])},
              "except_when": {"type": "string", "enum": sorted(cat["exceptions"])},
              "message": {"type": "string", "maxLength": R.MAX_MESSAGE}}
    keys = ["decision", "evidence", "applies_when", "must_hold", "except_when", "message"]
    add = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["add"]}, **common},
           "required": keys, "additionalProperties": False}
    revise = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["revise"]}, **common,
                                               "target_rule": {"type": "string", "enum": sorted(cat["rules"])}},
              "required": keys + ["target_rule"], "additionalProperties": False}
    none = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["none"]},
                                             "reason": {"type": "string"},
                                             "missing_facts": {"type": "array", "items": {"type": "string"}}},
            "required": ["decision", "reason"], "additionalProperties": False}
    return {"anyOf": [add, revise, none]}


def prompt_section(base: dict) -> str:
    """The template the model fills in, listing exactly the values the validator accepts."""
    cat = catalogue(base)
    lines = ["### Rule proposal (rule_proposal)",
             "Return exactly one of three answers. Copy every listed value exactly.", "",
             "Active rules (target_rule for revise):"]
    lines += [f"- {rid}: {doc}" for rid, doc in cat["rules"].items()]
    lines += ["", "Conditions (must_hold). Each reads only the listed relations:"]
    for cid, c in cat["conditions"].items():
        lines.append(f"- {cid} [applies_when: {c['operation']}; except_when: {' | '.join(c['exceptions'])}; "
                     f"message placeholders: {', '.join('{?' + p + '}' for p in c['placeholders'])}]")
        lines.append(f"  holds when {c['describe']}; relations: {', '.join(c['facts'])}")
    lines += ["", "Relations (facts the checker extracts):"]
    lines += [f"- {f}: {doc}" for f, doc in cat["relations"].items()]
    lines += ["", "Exceptions (except_when):"]
    lines += [f"- {e}: {doc}" for e, doc in cat["exceptions"].items()]
    lines += ["", "Answers:",
              '1. add: {"decision": "add", "evidence": {"line": <line in your answer>, "snippet": "<exact text '
              'copied from your answer>"}, "applies_when": "<operation>", "must_hold": "<condition>", '
              '"except_when": "<exception>", "message": "<short message for the model, <= 300 characters>"}',
              '2. revise: the same fields plus "target_rule": "<active rule ID>"; use it when an active rule '
              'should also catch this error.',
              '3. none: {"decision": "none", "reason": "<why no change>"}; add "missing_facts": [...] only if '
              'the error needs a relation that is not listed.', "",
              "Rules for the answer:",
              "- evidence.snippet must be copied character for character from your answer above; it is checked.",
              "- Choose a logging condition only if the snippet is the concrete logging call that uses the new "
              "parameter (for example log.debug(\"x \" + x)).",
              "- If an active rule already reports this error exactly, fix the code and keep the rules: answer none.",
              "- If no listed condition describes the observed error, answer none.", "",
              "Example of a correct none: your answer removed `public` from the class and R1 already reports "
              "\"R1 modifiers of class Example changed from 'public' to '(none)'\". The error is already covered, so:",
              '{"decision": "none", "reason": "R1 already reports the changed class modifier; only the code needs '
              'fixing."}']
    return "\n".join(lines)


class Evidence(BaseModel):
    model_config = {"extra": "forbid"}
    line: int | None = None
    snippet: str


class RuleProposal(BaseModel):
    model_config = {"extra": "forbid"}
    decision: Literal["add", "revise", "none"]
    reason: str = ""
    missing_facts: list[str] = Field(default_factory=list)
    target_rule: str | None = None
    evidence: Evidence | None = None
    applies_when: str | None = None
    must_hold: str | None = None
    except_when: str | None = None
    message: str = ""


def _norm(text: str) -> str:
    return " ".join(text.split())


def check_evidence(evidence: Evidence, answer: str | None) -> dict:
    """The snippet must occur in the answer (whitespace-insensitive); the line is informational."""
    text = evidence.snippet
    if '\\"' in text or "\\n" in text:  # copied from the JSON form of the answer
        text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")
    evidence = evidence.model_copy(update={"snippet": text})
    snippet = _norm(evidence.snippet)
    if not snippet or answer is None:
        raise R.ProposalError("evidence_not_found", "empty snippet or no parsed answer")
    if snippet not in _norm(answer):
        raise R.ProposalError("evidence_not_found", evidence.snippet[:120])
    first = _norm(evidence.snippet.strip().splitlines()[0])
    lines = [i + 1 for i, row in enumerate(answer.splitlines()) if first and first in _norm(row)]
    return {"found": True, "snippet_lines": lines,
            "line_matches": evidence.line in lines if evidence.line is not None else None}


def to_constraint(p: RuleProposal, base: dict, answer: str | None) -> tuple[dict, dict]:
    """Validate an add/revise answer against the catalogue; returns (constraint, evidence check)."""
    cat = catalogue(base)
    missing = [k for k in ("evidence", "applies_when", "must_hold", "except_when") if getattr(p, k) in (None, "")]
    if p.decision == "revise" and not p.target_rule:
        missing.append("target_rule")
    if missing or not p.message.strip():
        raise R.ProposalError("missing_fields", ", ".join(missing + ([] if p.message.strip() else ["message"])))
    if p.decision == "revise" and p.target_rule not in cat["rules"]:
        raise R.ProposalError("unknown_target_rule", str(p.target_rule))
    cond = cat["conditions"].get(p.must_hold)
    if cond is None:
        raise R.ProposalError("unknown_condition", str(p.must_hold))
    if p.applies_when != cond["operation"]:
        raise R.ProposalError("wrong_operation", f"{p.applies_when} for {p.must_hold}")
    if p.except_when not in cond["exceptions"]:
        raise R.ProposalError("unknown_exception", str(p.except_when))
    message = p.message.strip()
    used = set(re.findall(r"\{\?(\w+)\}", message))
    if "\n" in message or len(message) > R.MAX_MESSAGE or used - set(cond["placeholders"]) \
            or re.search(r"[{}]", re.sub(r"\{\?\w+\}", "", message)):
        raise R.ProposalError("bad_message", message[:80])
    evidence = check_evidence(p.evidence, answer)
    if cond["template"] == "new_parameter_used_only_in_role" and cond["params"].get("role") == "logging" \
            and not LOGGING_CALL.search(p.evidence.snippet):
        raise R.ProposalError("evidence_not_a_logging_use", p.evidence.snippet[:120])
    constraint = {"kind": "template", "template": cond["template"], "params": dict(cond["params"]),
                  "exception": p.except_when, "message": message, "must_hold": p.must_hold,
                  "applies_when": p.applies_when, "required_facts": list(cond["facts"]),
                  "evidence": p.evidence.model_dump(), "prompt_version": PROMPT_VERSION}
    return constraint, evidence


def apply(base: dict, p: RuleProposal, proposal_id: str, answer: str | None) -> tuple[dict, str, dict]:
    """New base with the proposal applied: (base, changed rule ID, evidence check). Pure."""
    if p.decision == "none":
        raise R.ProposalError("none", p.reason)
    constraint, evidence = to_constraint(p, base, answer)
    new = copy.deepcopy(base)
    if p.decision == "add":
        taken = {r["id"] for r in new["rules"]}
        rid = next(f"X{i}" for i in range(1, 1000) if f"X{i}" not in taken)
        new["rules"].append({"id": rid, "origin": "D2:" + proposal_id, "constraints": [constraint]})
        return new, rid, evidence
    rule = next(r for r in new["rules"] if r["id"] == p.target_rule)
    same = [k for k, c in enumerate(rule["constraints"]) if c["kind"] == "template" and c["template"] == constraint["template"]]
    if same:
        rule["constraints"][same[0]] = constraint
    else:
        rule["constraints"].append(constraint)
    rule["origin"] = rule["origin"] + "+D2:" + proposal_id
    return new, rule["id"], evidence


def operation_of(p: RuleProposal, base: dict) -> str:
    return catalogue(base)["conditions"][p.must_hold]["operation"]
