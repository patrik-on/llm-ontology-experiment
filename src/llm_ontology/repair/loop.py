"""Repair loop with three variants (C, D1, D2) that share one first attempt.

Per task, in a fixed order:

1. attempt 1 is generated **once** from the common prompt (same instruction, same project
   facts block, same settings) and handed to C, D1 and D2;
2. each variant checks it with the same public checker; on the first repairable failure it
   makes one analysis call (same token limit; D2 has one extra optional field for a rule
   proposal) and then up to two repair attempts (at most 3 attempts in total);
3. D1 and D2 add the reports of their rule base to the feedback; C gets none (its reports are
   still computed and stored as a shadow measurement);
4. a D2 proposal is verified independently on labelled examples the model never sees and,
   if accepted, becomes active at the next task of a different group. The current task is
   repaired with the version it started with.

The loop checks only with public information. Final scores come from ``task.score`` (the
existing evaluator) after the loop, for the answer after 1, 2 and 3 attempts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from pydantic import BaseModel

from llm_ontology.repair import rules as R
from llm_ontology.repair.state import RuleState
from llm_ontology.repair.verify import Example

VARIANTS = ("C", "D1", "D2")
MAX_ATTEMPTS = 3
MAX_TOOL_MESSAGES = 5
MAX_RULE_MESSAGES = 5
MAX_MESSAGE_CHARS = 300


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class Generation:
    text: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    seconds: float = 0.0
    meta: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str

    def generate(self, prompt: str, schema: dict, max_tokens: int) -> Generation: ...


@dataclass
class Check:
    status: str            # PASSED | INVALID_OUTPUT | INVALID_JAVA | NO_OP | OPERATION_MISSING | ...
    success: bool
    repairable: bool       # False = infrastructure failure: the cell stops and stays unresolved
    tool: str
    messages: list[str]
    source: str | None = None  # parsed code, if any
    seconds: float = 0.0


class Task(Protocol):
    kind: str

    def cases(self) -> list[dict]: ...
    def group(self, case: dict) -> str: ...
    def prompt(self, case: dict) -> str: ...
    def schema(self) -> dict: ...
    def check(self, case: dict, raw: str, workdir: Path) -> Check: ...
    def facts(self, case: dict, source: str): ...
    def score(self, case: dict, raw: str, workdir: Path) -> dict: ...


class Diagnosis(BaseModel):
    model_config = {"extra": "forbid"}
    location: str
    cause: str


class DiagnosisWithRule(Diagnosis):
    rule_proposal: R.RuleProposal | None = None


AUTHOR_INSTRUCTION = (
    "Compare the task, your answer and the diagnostics. Name the concrete place and explain the cause "
    "that the available facts support. If a rule that applies to a later task can be derived from this "
    "cause, propose exactly one addition or modification. State when the rule applies, an example of a "
    "legitimate exception, the facts it needs, the condition (as one of the templates below) and a short "
    "message for the model. Use only the available vocabulary. If facts are missing, name them in "
    "missing_facts. If the rule already exists or the cause is not sufficiently supported, return "
    "decision \"none\".")


def _clip(items: list[str], limit: int) -> tuple[list[str], int]:
    seen, out = set(), []
    for item in items:
        item = " ".join(item.split())[:MAX_MESSAGE_CHARS]
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:limit], len(out)


def feedback_text(k: int, raw: str, check: Check, reports: list[str] | None, diagnosis: dict | None,
                  version: str | None) -> str:
    tool, total = _clip(check.messages, MAX_TOOL_MESSAGES)
    lines = [f"### Previous answer (attempt {k} of {MAX_ATTEMPTS})", raw, "", f"### Feedback on attempt {k}",
             f"Status: {check.status}", f"Tool output ({check.tool}), {len(tool)} of {total} messages:"]
    lines += ["- " + m for m in tool] or ["- (none)"]
    if reports is not None:
        rule, rtotal = _clip(reports, MAX_RULE_MESSAGES)
        lines.append(f"Rule checks ({version}), {len(rule)} of {rtotal} violations:")
        lines += ["- " + m for m in rule] or ["- (none)"]
    if diagnosis:
        lines += ["Diagnosis of the first failure:", "Location: " + diagnosis["location"],
                  "Cause: " + diagnosis["cause"]]
    lines += ["Fix the reported problems. Keep everything else unchanged.",
              "Return the complete answer in the same JSON format as before."]
    return "\n".join(lines)


def analysis_prompt(variant: str, prompt1: str, raw: str, check: Check, reports: list[str] | None,
                    base: dict | None, task_kind: str) -> str:
    tool, total = _clip(check.messages, MAX_TOOL_MESSAGES)
    lines = ["You are analysing a failed answer. Do not write a new answer.", "", "### Task", prompt1, "",
             "### Your answer", raw, "", "### Diagnostics", f"Status: {check.status}",
             f"Tool output ({check.tool}), {len(tool)} of {total} messages:", *["- " + m for m in tool]]
    if reports is not None:
        rule, rtotal = _clip(reports, MAX_RULE_MESSAGES)
        lines += [f"Rule checks, {len(rule)} of {rtotal} violations:", *(["- " + m for m in rule] or ["- (none)"])]
    lines += ["", "### Instructions"]
    if variant == "D2":
        lines += [AUTHOR_INSTRUCTION, "", "Current rules:", R.describe_base(base), "",
                  "Templates (closed list):", R.template_catalogue(task_kind), "",
                  "Return JSON with: location, cause, rule_proposal (decision add|modify|none, target_rule for "
                  "modify, template, params, exception, applies_when, exception_example, required_facts, "
                  "missing_facts, message)."]
    else:
        lines += ["Compare the task, your answer and the diagnostics. Name the concrete place and explain the "
                  "cause that the available facts support.", "", "Return JSON with: location, cause."]
    return "\n".join(lines)


class Loop:
    def __init__(self, root: Path, task: Task, provider: Provider, *, d1: dict, pool: list[Example],
                 max_new_tokens: int, analysis_tokens: int, variants=VARIANTS):
        self.root, self.task, self.provider = Path(root), task, provider
        self.d1, self.pool = d1, pool
        self.max_new_tokens, self.analysis_tokens = max_new_tokens, analysis_tokens
        self.variants = tuple(variants)
        self.d1_sha = R.base_hash(d1)
        self.state = RuleState(self.root / "rulebase_d2", d1) if "D2" in self.variants else None
        self.calls_path = self.root / "calls.jsonl"

    # ----- model calls -----------------------------------------------------------------
    def _call(self, out: Path, prompt: str, schema: dict, max_tokens: int, *, kind: str, case: str,
              variant: str, attempt: int) -> str:
        """Generate once; a stored response is reused on resume and never charged twice."""
        if (out / "raw.txt").exists() and (out / "prompt.txt").exists():
            if (out / "prompt.txt").read_text(encoding="utf-8") != prompt:
                raise ValueError("Stored prompt differs on resume: " + str(out))
            return (out / "raw.txt").read_text(encoding="utf-8")
        out.mkdir(parents=True, exist_ok=True)
        (out / "prompt.txt").write_text(prompt, encoding="utf-8")
        gen = self.provider.generate(prompt, schema, max_tokens)
        (out / "raw.txt").write_text(gen.text, encoding="utf-8")
        write_json(out / "generation.json", {"prompt_sha256": sha(prompt), "response_sha256": sha(gen.text),
                                             "prompt_tokens": gen.prompt_tokens, "output_tokens": gen.output_tokens,
                                             "seconds": gen.seconds, "meta": gen.meta})
        with self.calls_path.open("a", encoding="utf-8") as handle:
            handle.write(R.canonical({"case": case, "variant": variant, "kind": kind, "attempt": attempt,
                                      "prompt_tokens": gen.prompt_tokens, "output_tokens": gen.output_tokens,
                                      "seconds": gen.seconds}) + "\n")
        return gen.text

    # ----- rules -----------------------------------------------------------------------
    def _reports(self, case: dict, check: Check, base: dict, out: Path) -> list[str]:
        rows, error = [], None
        start = perf_counter()
        if check.source is not None:
            try:
                rows = R.findings(self.task.facts(case, check.source), base)
            except Exception as exc:  # facts unavailable: the variant gets no rule reports
                error = str(exc)[:300]
        write_json(out / "rules.json", {"findings": rows, "error": error, "seconds": perf_counter() - start,
                                        "base_sha256": R.base_hash(base)})
        return [r["message"] for r in R.violations(rows)]

    # ----- one task ----------------------------------------------------------------------
    def run_case(self, case: dict) -> None:
        cid, group = case["id"], self.task.group(case)
        croot = self.root / "cases" / cid
        prompt1 = self.task.prompt(case)
        raw1 = self._call(croot / "shared" / "attempt-1", prompt1, self.task.schema(), self.max_new_tokens,
                          kind="generate", case=cid, variant="shared", attempt=1)
        for variant in self.variants:
            vroot = croot / variant
            if (vroot / "completion.json").exists():
                continue
            if R.base_hash(self.d1) != self.d1_sha:
                raise ValueError("D1 base changed during the run")
            version, base = None, None
            if variant == "D1":
                version, base = "D1", self.d1
            elif variant == "D2":
                number, base = self.state.begin_task(cid, group)
                version = f"D2 v{number}"
            shadow = self.d1 if variant == "C" else base
            attempts, raw, diagnosis, status, feedback = [], raw1, None, "failed", ""
            for k in range(1, MAX_ATTEMPTS + 1):
                adir = vroot / f"attempt-{k}"
                if k > 1:
                    prompt = prompt1 + "\n\n" + feedback
                    (adir).mkdir(parents=True, exist_ok=True)
                    (adir / "feedback.txt").write_text(feedback, encoding="utf-8")
                    raw = self._call(adir, prompt, self.task.schema(), self.max_new_tokens,
                                     kind="generate", case=cid, variant=variant, attempt=k)
                adir.mkdir(parents=True, exist_ok=True)
                check = self.task.check(case, raw, adir / "check")
                write_json(adir / "check.json", {**check.__dict__, "source": None})
                attempts.append({"attempt": k, "response_sha256": sha(raw), "status": check.status})
                messages = self._reports(case, check, shadow, adir)
                reports = None if variant == "C" else messages
                if check.success:
                    status = "passed"
                    break
                if not check.repairable:
                    status = "unresolved"
                    break
                if k == MAX_ATTEMPTS:
                    break
                if diagnosis is None:
                    diagnosis = self._analyse(variant, case, group, prompt1, raw, check, reports, base, vroot)
                feedback = feedback_text(k, raw, check, reports, diagnosis, version)
            write_json(vroot / "completion.json", {"status": status, "attempts": attempts, "base": version,
                                                   "base_sha256": R.base_hash(base) if base else None})

    def _analyse(self, variant, case, group, prompt1, raw, check, reports, base, vroot) -> dict:
        model = DiagnosisWithRule if variant == "D2" else Diagnosis
        prompt = analysis_prompt(variant, prompt1, raw, check, reports, base, self.task.kind)
        text = self._call(vroot / "analysis", prompt, model.model_json_schema(), self.analysis_tokens,
                          kind="analysis", case=case["id"], variant=variant, attempt=1)
        try:
            payload = json.loads(text)
            diagnosis = {"location": str(payload.get("location", ""))[:MAX_MESSAGE_CHARS],
                         "cause": str(payload.get("cause", ""))[:2 * MAX_MESSAGE_CHARS]}
            proposal = payload.get("rule_proposal") if variant == "D2" else None
        except (ValueError, AttributeError):
            diagnosis, proposal = {"location": "(unparseable analysis)", "cause": ""}, None
        write_json(vroot / "analysis" / "diagnosis.json", diagnosis)
        if variant == "D2":
            trigger = None
            if check.source is not None:
                try:
                    trigger = self.task.facts(case, check.source)
                except Exception:
                    trigger = None
            evidence = {"prompt_sha256": sha(prompt1), "answer_sha256": sha(raw), "status": check.status,
                        "tool_messages": check.messages[:MAX_TOOL_MESSAGES], "rule_reports": reports,
                        "diagnosis": diagnosis}
            entry = self.state.propose(task=case["id"], group=group,
                                       proposal=proposal if proposal else {"decision": "none"},
                                       evidence=evidence, trigger=trigger, pool=self.pool)
            write_json(vroot / "analysis" / "proposal.json", entry)
        return diagnosis

    def run(self, cases: list[dict]) -> None:
        for case in cases:
            self.run_case(case)

    # ----- final scoring -------------------------------------------------------------
    def score(self, cases: list[dict]) -> dict:
        """Existing evaluator on the answer after 1, 2 and 3 attempts (each distinct answer once)."""
        table: dict = {}
        for case in cases:
            croot = self.root / "cases" / case["id"]
            cache_path = croot / "scores.json"
            cache = read_json(cache_path) if cache_path.exists() else {}
            for variant in self.variants:
                comp = croot / variant / "completion.json"
                if not comp.exists():
                    continue
                completion = read_json(comp)
                raws = []
                for a in completion["attempts"]:
                    path = (croot / "shared" / "attempt-1" / "raw.txt" if a["attempt"] == 1
                            else croot / variant / f"attempt-{a['attempt']}" / "raw.txt")
                    raws.append(path.read_text(encoding="utf-8"))
                row = {}
                unresolved = completion["status"] == "unresolved"
                for limit in range(1, MAX_ATTEMPTS + 1):
                    index = min(limit, len(raws))
                    if unresolved and index == len(raws):
                        row[f"S@{limit}"] = False  # the last answer could not be checked: unresolved
                        continue
                    key = sha(raws[index - 1])
                    if key not in cache:
                        cache[key] = self.task.score(case, raws[index - 1], croot / "final" / key[:16])
                    row[f"S@{limit}"] = bool(cache[key]["success"])
                row["status"] = completion["status"]
                row["calls"] = len(completion["attempts"]) - 1 + int((croot / variant / "analysis").exists())
                table.setdefault(case["id"], {})[variant] = row
            write_json(cache_path, cache)
        return table
