"""Stand-ins for the mechanism check without Ollama or Java (tests and ``--mock`` runs).

``ScriptedProvider`` answers from a Python function, ``SyntheticRefactoringTask`` uses the real
fact extraction and rule bases but replaces RefactoringMiner with a comparison to a known
correct answer. Results produced with them are a check of the mechanism, never model results.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from llm_ontology.repair import java_facts
from llm_ontology.repair.loop import Check, Generation


def _norm(text: str) -> str:
    return " ".join(text.split())


class ScriptedProvider:
    name = "scripted-mock"

    def __init__(self, respond: Callable[[str, dict], str]):
        self.respond, self.prompts = respond, []

    def generate(self, prompt: str, schema: dict, max_tokens: int, temperature: float = 0.0) -> Generation:
        self.prompts.append(prompt)
        text = self.respond(prompt, schema)
        return Generation(text, prompt_tokens=len(prompt.split()), output_tokens=len(text.split()), seconds=0.0,
                          meta={"mock": True})


class SyntheticRefactoringTask:
    kind = "refactoring"

    def __init__(self, cases: list[dict]):
        self._cases = cases

    @classmethod
    def from_file(cls, path: Path) -> "SyntheticRefactoringTask":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def cases(self):
        return self._cases

    def group(self, case):
        return case["group"]

    def prompt(self, case):
        return ("Refactor the Java code. Return JSON {file_path, refactored_code}.\n"
                f"Requested operation: {case['operation']}\nExact requested change: {case['request']}\n"
                f"Allowed file_path: {case['file_path']}\n### Input\n{case['before']}")

    def schema(self):
        return {"type": "object", "properties": {"file_path": {"type": "string"},
                                                 "refactored_code": {"type": "string"}}}

    def _source(self, case, raw):
        payload = json.loads(raw)
        if payload.get("file_path") != case["file_path"]:
            raise ValueError("Wrong allowed path")
        return payload["refactored_code"]

    def check(self, case, raw, workdir):
        try:
            source = self._source(case, raw)
        except Exception as exc:
            return Check("INVALID_OUTPUT", False, True, "parser", [str(exc)[:300]])
        if _norm(source) == _norm(case["expected"]):
            return Check("PASSED", True, True, "mock-detector", [], source)
        return Check("OPERATION_MISSING", False, True, "mock-detector",
                     ["Requested: " + _norm(case["request"]), "Detected instead: Add Parameter"], source)

    def source(self, case, raw):
        return self._source(case, raw)

    def facts(self, case, source):
        return java_facts.refactoring_graph(case["before"], source, case["request"], int(case["target_start"]))

    def score(self, case, raw, workdir):
        check = self.check(case, raw, workdir)
        return {"success": check.success, "status": check.status}


# ----- the hand-prepared mechanism scenario (tests and ``--mock``) ------------------------
MESSAGE = "{?m} uses the new parameter '{?new}' only for {?role}; the computation must use it."
REFINE = {"decision": "revise", "target_rule": "R2",
          "evidence": {"line": 4, "snippet": 'log.info("rate " + rate);'},
          "applies_when": "Parameterize Variable", "must_hold": "new_parameter_used_only_in_role:logging",
          "except_when": "method_is_logging_helper", "message": MESSAGE}
NO_EXCEPTION = {"decision": "add", "evidence": {"line": 4, "snippet": 'log.debug("limit=" + limit);'},
                "applies_when": "Parameterize Variable", "must_hold": "new_parameter_used_only_in_role:logging",
                "except_when": "none", "message": MESSAGE}
SCENARIO = {"loop-1": NO_EXCEPTION, "loop-2": REFINE}


def scripted(cases: list[dict], proposals: dict[str, dict]) -> Callable[[str, dict], str]:
    """Bad first answer everywhere; a repair is correct only if the feedback names the
    logging-only problem, which only the accepted D2 rule reports."""
    by_class = {c["file_path"].split("/")[-1][:-5]: c for c in cases}

    def respond(prompt, schema):
        case = next(c for name, c in by_class.items() if f"class {name}" in prompt)
        if prompt.startswith("You are analysing a failed answer"):
            payload = {"location": "target method", "cause": "the new parameter is not used in the computation"}
            if "rule_proposal" in schema.get("properties", {}):
                payload["rule_proposal"] = proposals.get(case["id"], {"decision": "none", "covered_by": {"rule": "none", "report": ""},
                                                                         "reason": "no listed condition fits"})
            return json.dumps(payload)
        good = "only for logging; the computation must use it" in prompt
        return json.dumps({"file_path": case["file_path"], "refactored_code": case["expected" if good else "bad"]})
    return respond


def mechanism(cases_path: Path, pool_path: Path):
    from llm_ontology.repair.verify import load_pool

    task = SyntheticRefactoringTask.from_file(cases_path)
    return task, ScriptedProvider(scripted(task.cases(), SCENARIO)), load_pool(pool_path)
