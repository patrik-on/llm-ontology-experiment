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

Catalogue versions (prepared by a person; the model only combines what is listed):
``c1`` the conditions of the first pilot, one condition per rule; ``c2`` adds general conditions
on the requested method and the method that held the variable (java_facts v2) and lets a
rule combine at most two conditions (all must hold).

A ``none`` that claims an active rule already reports the error must name that report in
``covered_by`` (rule ID and the report text; ``{"rule": "none", "report": ""}`` when no active
rule reports it; the field is required from prompt v4 on, because with constrained decoding
the model never filled the optional field); the validator checks that this rule produced
exactly that report for the current answer. It cannot check whether the reason restates the
report's meaning correctly.
"""
from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import BaseModel, Field

from llm_ontology.repair import rules as R
from llm_ontology.repair.java_facts import LOG_METHODS

PROMPT_VERSION = "d2-rule-template-v4"  # v3: covered_by for none, catalogue versions; v4: covered_by required
CATALOGUES = {
    "c1": ["new_parameter_used_only_in_role", "old_local_still_declared", "mutated_argument_from_factory"],
    "c2": ["new_parameter_used_only_in_role", "old_local_still_declared", "mutated_argument_from_factory",
           "target_method_missing_in_input", "requested_signature_missing_in_output",
           "variable_kept_local_in_source_method"],
}
MAX_CONDITIONS = {"c1": 1, "c2": 2}
DEFAULT_CATALOGUE = "c1"
# "R2 already reports ...": a rule ID followed, in the same clause, by a reporting verb (not negated)
RULE_CLAIM = re.compile(r"\b([A-Z]\d+)\b([^.;:]*?)\b(report|reports|reported|reporting|flags|flagged|catches|"
                        r"caught|covers|covered|detects|detected)\b", re.I)
NEGATION = re.compile(r"\b(not|cannot|can't|doesn't|does not|no|never|fails? to)\b", re.I)

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
    "lo:requestedSignature": "name and parameter types of the method the request names",
    "lo:targetMethodInInput": "true if the supplied input declares a method with the requested name",
    "lo:targetSignatureInOutput": "true if your output declares a method with the requested name and parameter types",
    "lo:sourceMethodAfter": "the method that held the old variable in the input, as it appears in your output",
}
EXCEPTION_FACTS = {"method_is_logging_helper": "lo:isLoggingHelper", "inside_expected_exception": "lo:inExpectedException"}
LOGGING_CALL = re.compile(r"\b(" + "|".join(sorted(LOG_METHODS)) + r")\s*\(")


def conditions(task: str, catalogue: str = DEFAULT_CATALOGUE) -> dict[str, dict]:
    """Template x fixed parameter values -> one named condition each (templates of the catalogue)."""
    out = {}
    for name, spec in R.TEMPLATES.items():
        if spec["task"] != task or name not in CATALOGUES[catalogue]:
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
                parts.append(base.get("rule_docs", {}).get(rule["id"]) or R.RULE_DOCS.get(rule["id"], "handwritten rule"))
            else:
                parts.append(f"added condition {c['must_hold']} (exception {c['exception']})")
        out[rule["id"]] = "; ".join(parts)
    return out


def catalogue(base: dict, catalogue: str = DEFAULT_CATALOGUE) -> dict:
    conds = conditions(base["task"], catalogue)
    exceptions = sorted({x for c in conds.values() for x in c["exceptions"]})
    facts = sorted({f for c in conds.values() for f in c["facts"]} | {EXCEPTION_FACTS[e] for e in exceptions
                                                                        if e in EXCEPTION_FACTS})
    return {"version": PROMPT_VERSION, "catalogue": catalogue, "max_conditions": MAX_CONDITIONS[catalogue],
            "task": base["task"], "conditions": conds,
            "operations": sorted({c["operation"] for c in conds.values()}),
            "exceptions": {e: R.EXCEPTION_DOCS[e] for e in exceptions},
            "relations": {f: FACT_DOCS[f] for f in facts if f in FACT_DOCS}, "rules": rule_ids(base)}


def schema(base: dict, catalogue_version: str = DEFAULT_CATALOGUE) -> dict:
    """JSON schema of ``rule_proposal`` with exactly the enumerations of the catalogue."""
    cat = catalogue(base, catalogue_version)
    must_hold = {"type": "string", "enum": sorted(cat["conditions"])}
    if cat["max_conditions"] > 1:
        must_hold = {"type": "array", "items": must_hold, "minItems": 1, "maxItems": cat["max_conditions"]}
    evidence = {"type": "object", "properties": {"line": {"type": "integer"}, "snippet": {"type": "string"}},
                "required": ["snippet"], "additionalProperties": False}
    common = {"evidence": evidence, "applies_when": {"type": "string", "enum": cat["operations"]},
              "must_hold": must_hold,
              "except_when": {"type": "string", "enum": sorted(cat["exceptions"])},
              "message": {"type": "string", "maxLength": R.MAX_MESSAGE}}
    keys = ["decision", "evidence", "applies_when", "must_hold", "except_when", "message"]
    add = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["add"]}, **common},
           "required": keys, "additionalProperties": False}
    revise = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["revise"]}, **common,
                                               "target_rule": {"type": "string", "enum": sorted(cat["rules"])}},
              "required": keys + ["target_rule"], "additionalProperties": False}
    none = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["none"]},
                                             "covered_by": {"type": "object", "additionalProperties": False,
                                                            "required": ["rule", "report"],
                                                            "properties": {"rule": {"type": "string",
                                                                                    "enum": sorted(cat["rules"]) + ["none"]},
                                                                           "report": {"type": "string"}}},
                                             "reason": {"type": "string"},
                                             "missing_facts": {"type": "array", "items": {"type": "string"}}},
            "required": ["decision", "covered_by", "reason"], "additionalProperties": False}
    return {"anyOf": [add, revise, none]}


def prompt_section(base: dict, catalogue_version: str = DEFAULT_CATALOGUE) -> str:
    """The template the model fills in, listing exactly the values the validator accepts."""
    cat = catalogue(base, catalogue_version)
    combine = cat["max_conditions"] > 1
    lines = ["### Rule proposal (rule_proposal)",
             "Return exactly one of three answers. Copy every listed value exactly.", "",
             "Active rules (target_rule for revise):"]
    lines += [f"- {rid}: {doc}" for rid, doc in cat["rules"].items()]
    lines += ["", ("Conditions (must_hold: a list of 1 or 2 of them; with 2 the rule reports only when both hold). "
                   if combine else "Conditions (must_hold). ") + "Each reads only the listed relations:"]
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
              'copied from your answer>"}, "applies_when": "<operation>", "must_hold": '
              + ('["<condition>", "<optional second condition>"]' if combine else '"<condition>"') + ', '
              '"except_when": "<exception>", "message": "<short message for the model, <= 300 characters>"}',
              '2. revise: the same fields plus "target_rule": "<active rule ID>"; use it when an active rule '
              'should also catch this error.',
              '3. none: {"decision": "none", "covered_by": {"rule": "<rule ID or none>", "report": "<report or empty>"}, '
              '"reason": "<why no change>"}; add "missing_facts": [...] only if the error needs a relation that is '
              'not listed.',
              '   covered_by is required. If an active rule already reports this error, give its ID and copy that '
              'report exactly from Rule checks; it is checked: the rule must have produced exactly this report for '
              'your answer. Otherwise write {"rule": "none", "report": ""} and do not claim in the reason that a '
              'rule reports the error.', "",
              "Rules for the answer:",
              "- evidence.snippet must be copied character for character from your answer above; it is checked.",
              "- Choose a logging condition only if the snippet is the concrete logging call that uses the new "
              "parameter (for example log.debug(\"x \" + x)).",
              "- If an active rule already reports this error exactly, fix the code and keep the rules: answer none.",
              "- If no listed condition describes the observed error, answer none.", "",
              "Example of a correct none: your answer removed `public` from the class and R1 already reports "
              "\"R1 modifiers of class Example changed from 'public' to '(none)'\". The error is already covered, so:",
              '{"decision": "none", "covered_by": {"rule": "R1", "report": "R1 modifiers of class Example changed from '
              '\'public\' to \'(none)\'. The requested operation does not change modifiers; restore them."}, '
              '"reason": "R1 already reports the changed class modifier; only the code needs fixing."}',
              'A none with {"rule": "none", "report": ""} is also correct when no listed condition can express the '
              "observed error; then say so in the reason."]
    return "\n".join(lines)


class Evidence(BaseModel):
    model_config = {"extra": "forbid"}
    line: int | None = None
    snippet: str


class CoveredBy(BaseModel):
    model_config = {"extra": "forbid"}
    rule: str
    report: str


class RuleProposal(BaseModel):
    model_config = {"extra": "forbid"}
    decision: Literal["add", "revise", "none"]
    reason: str = ""
    covered_by: CoveredBy | None = None
    missing_facts: list[str] = Field(default_factory=list)
    target_rule: str | None = None
    evidence: Evidence | None = None
    applies_when: str | None = None
    must_hold: str | list[str] | None = None
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


def _conditions_of(p: RuleProposal, cat: dict) -> list[str]:
    names = [p.must_hold] if isinstance(p.must_hold, str) else list(p.must_hold or [])
    if not names:
        raise R.ProposalError("missing_fields", "must_hold")
    if len(names) > cat["max_conditions"] or len(set(names)) != len(names):
        raise R.ProposalError("bad_combination", f"{names} (at most {cat['max_conditions']} distinct conditions)")
    if isinstance(p.must_hold, list) and cat["max_conditions"] == 1:
        raise R.ProposalError("bad_combination", "this catalogue takes one condition as a string")
    for name in names:
        if name not in cat["conditions"]:
            raise R.ProposalError("unknown_condition", str(name))
    return names


def to_constraint(p: RuleProposal, base: dict, answer: str | None,
                  catalogue_version: str = DEFAULT_CATALOGUE) -> tuple[dict, dict]:
    """Validate an add/revise answer against the catalogue; returns (constraint, evidence check)."""
    cat = catalogue(base, catalogue_version)
    missing = [k for k in ("evidence", "applies_when", "must_hold", "except_when") if getattr(p, k) in (None, "", [])]
    if p.decision == "revise" and not p.target_rule:
        missing.append("target_rule")
    if missing or not p.message.strip():
        raise R.ProposalError("missing_fields", ", ".join(missing + ([] if p.message.strip() else ["message"])))
    if p.decision == "revise" and p.target_rule not in cat["rules"]:
        raise R.ProposalError("unknown_target_rule", str(p.target_rule))
    names = _conditions_of(p, cat)
    conds = [cat["conditions"][n] for n in names]
    operations = {c["operation"] for c in conds}
    if len(operations) != 1:
        raise R.ProposalError("bad_combination", f"conditions of different operations: {sorted(operations)}")
    if p.applies_when not in operations:
        raise R.ProposalError("wrong_operation", f"{p.applies_when} for {names}")
    allowed = set.intersection(*(set(c["exceptions"]) for c in conds))
    if p.except_when not in allowed:
        raise R.ProposalError("unknown_exception", str(p.except_when))
    placeholders = {x for c in conds for x in c["placeholders"]}
    message = p.message.strip()
    used = set(re.findall(r"\{\?(\w+)\}", message))
    if "\n" in message or len(message) > R.MAX_MESSAGE or used - placeholders \
            or re.search(r"[{}]", re.sub(r"\{\?\w+\}", "", message)):
        raise R.ProposalError("bad_message", message[:80])
    evidence = check_evidence(p.evidence, answer)
    if any(c["template"] == "new_parameter_used_only_in_role" and c["params"].get("role") == "logging" for c in conds) \
            and not LOGGING_CALL.search(p.evidence.snippet):
        raise R.ProposalError("evidence_not_a_logging_use", p.evidence.snippet[:120])
    facts = sorted({f for c in conds for f in c["facts"]} |
                   ({EXCEPTION_FACTS[p.except_when]} if p.except_when in EXCEPTION_FACTS else set()))
    constraint = {"kind": "template", "template": conds[0]["template"], "params": dict(conds[0]["params"]),
                  "exception": p.except_when, "message": message,
                  "must_hold": p.must_hold if isinstance(p.must_hold, str) else list(names),
                  "applies_when": p.applies_when, "required_facts": facts if len(conds) > 1 else list(conds[0]["facts"]),
                  "evidence": p.evidence.model_dump(), "prompt_version": PROMPT_VERSION}
    if len(conds) > 1:
        constraint.update(parts=[{"template": c["template"], "params": dict(c["params"])} for c in conds],
                          catalogue=catalogue_version)
    return constraint, evidence


def check_none(p: RuleProposal, base: dict, reports: list[str] | None) -> dict:
    """A none that relies on an active rule must cite the exact report that rule produced now."""
    active = set(rule_ids(base))
    claimed = sorted({m.group(1) for m in RULE_CLAIM.finditer(p.reason) if not NEGATION.search(m.group(2))} & active)
    if p.covered_by is None:  # required in the schema (prompt v4), so the validator requires it too
        raise R.ProposalError("missing_covered_by", "none without covered_by")
    if p.covered_by.rule == "none":
        if claimed:
            raise R.ProposalError("uncited_rule_claim", f"reason names {claimed} without covered_by")
        return {"covered_by": None}
    rule, cited = p.covered_by.rule, _norm(p.covered_by.report)
    if rule not in active:
        raise R.ProposalError("unknown_target_rule", rule)
    if reports is None:
        raise R.ProposalError("covered_report_not_found", "no rule reports for this answer")
    own = [_norm(r) for r in reports if r.split(" ", 1)[0] == rule]
    first = cited.split(" ", 1)[0]
    if first in active and first != rule:  # the cited report belongs to another rule
        if any(_norm(r).startswith(cited.rstrip(" .…")) for r in reports):
            raise R.ProposalError("covered_rule_mismatch", f"report of {first} cited as {rule}")
        raise R.ProposalError("covered_report_not_found", p.covered_by.report[:160])
    if not cited.startswith(rule + " "):
        cited = _norm(rule + " " + cited)
    match = next((r for r in own if r == cited), None)
    if match is None and len(cited) >= 40:  # a report shortened at the end still names one declaration
        match = next((r for r in own if r.startswith(cited.rstrip(" .…"))), None)
    if match is None:
        body = cited.split(" ", 1)[-1]
        other = next((r for r in reports if _norm(r).split(" ", 1)[-1] == body), None)
        raise R.ProposalError("covered_rule_mismatch" if other else "covered_report_not_found", p.covered_by.report[:160])
    if claimed and set(claimed) != {rule}:
        raise R.ProposalError("uncited_rule_claim", f"reason names {claimed}, covered_by cites {rule}")
    return {"covered_by": {"rule": rule, "report": match}}


def apply(base: dict, p: RuleProposal, proposal_id: str, answer: str | None,
          catalogue_version: str = DEFAULT_CATALOGUE) -> tuple[dict, str, dict]:
    """New base with the proposal applied: (base, changed rule ID, evidence check). Pure."""
    if p.decision == "none":
        raise R.ProposalError("none", p.reason)
    constraint, evidence = to_constraint(p, base, answer, catalogue_version)
    new = copy.deepcopy(base)
    if p.decision == "add":
        taken = {r["id"] for r in new["rules"]}
        rid = next(f"X{i}" for i in range(1, 1000) if f"X{i}" not in taken)
        new["rules"].append({"id": rid, "origin": "D2:" + proposal_id, "constraints": [constraint]})
        return new, rid, evidence
    rule = next(r for r in new["rules"] if r["id"] == p.target_rule)
    key = (constraint["template"], repr(constraint.get("parts")))
    same = [k for k, c in enumerate(rule["constraints"]) if c["kind"] == "template"
            and (c["template"], repr(c.get("parts"))) == key]
    if same:
        rule["constraints"][same[0]] = constraint
    else:
        rule["constraints"].append(constraint)
    rule["origin"] = rule["origin"] + "+D2:" + proposal_id
    return new, rule["id"], evidence


def operation_of(p: RuleProposal, base: dict, catalogue_version: str = DEFAULT_CATALOGUE) -> str:
    cat = catalogue(base, catalogue_version)
    return cat["conditions"][_conditions_of(p, cat)[0]]["operation"]
