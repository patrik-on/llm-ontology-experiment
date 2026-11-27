"""D2 rule-base state: versions, proposal ledger, activation, freeze and resume.

Layout of ``<run>/rulebase_d2/``::

    versions/v0000.json   exact copy of the D1 base (hash-checked at init)
    versions/vNNNN.json   one file per accepted change
    ledger.jsonl          append-only; the only source of truth on resume

A version file becomes real only when its ``proposal`` entry is in the ledger, so a crash
between the two leaves an orphan file that the next write overwrites. Every task records
the version it started with (``task_start``); an accepted change is activated at the start
of the next task from a *different* group. ``freeze`` stops all later changes. One analysis
call per task gives at most one proposal per task, so ``task`` is the idempotency key: after
a resume the same change is never counted twice.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from rdflib import Graph

from llm_ontology.repair import proposal as P
from llm_ontology.repair import rules as R
from llm_ontology.repair.verify import Example, verify


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(R.canonical(entry) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class RuleState:
    def __init__(self, root: Path, d1: dict):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.ledger_path = self.root / "ledger.jsonl"
        if not self.ledger_path.exists():
            self.versions.mkdir(parents=True, exist_ok=True)
            _write_json(self.versions / "v0000.json", d1)
            _append(self.ledger_path, {"type": "init", "version": 0, "sha256": R.base_hash(d1)})
        v0 = self.load_version(0)
        if R.base_hash(v0) != R.base_hash(d1):
            raise ValueError("D2 v0 differs from the D1 base")
        self._replay()

    # ----- ledger replay -------------------------------------------------------------
    def _replay(self) -> None:
        self.entries = [json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line]
        self.active, self.latest, self.frozen = 0, 0, None
        self.pending_group: str | None = None  # group in which the newest unactivated change was accepted
        self.tasks: dict[str, dict] = {}
        self.proposals: dict[str, dict] = {}
        for e in self.entries:
            if e["type"] == "task_start":
                self.tasks[e["task"]] = e
                self.active = e["version"]
            elif e["type"] == "proposal":
                self.proposals[e["task"]] = e
                if e["decision"] == "accepted":
                    self.latest, self.pending_group = e["version"], e["group"]
            elif e["type"] == "freeze":
                self.frozen = e
        for e in self.entries:
            if e["type"] == "proposal" and e["decision"] == "accepted":
                path = self.versions / f"v{e['version']:04d}.json"
                if R.base_hash(json.loads(path.read_text(encoding="utf-8"))) != e["sha256"]:
                    raise ValueError("Committed D2 version changed on disk: " + path.name)

    def load_version(self, number: int) -> dict:
        return json.loads((self.versions / f"v{number:04d}.json").read_text(encoding="utf-8"))

    # ----- task lifecycle --------------------------------------------------------------
    def begin_task(self, task: str, group: str) -> tuple[int, dict]:
        """Version used for this whole task (rule reports, analysis and repair)."""
        if task in self.tasks:
            number = self.tasks[task]["version"]
            return number, self.load_version(number)
        number = self.active
        if self.frozen is not None:
            number = self.frozen["version"]
        elif self.latest > self.active and group != self.pending_group:
            number = self.latest
        _append(self.ledger_path, {"type": "task_start", "task": task, "group": group, "version": number,
                                   "sha256": R.base_hash(self.load_version(number))})
        self._replay()
        return number, self.load_version(number)

    def propose(self, *, task: str, group: str, proposal: dict | None, evidence: dict,
                trigger: Graph | None, pool: list[Example], answer: str | None = None) -> dict:
        """Record (and verify) the proposal of one task; returns the ledger entry."""
        if task in self.proposals:
            return self.proposals[task]
        if task not in self.tasks:
            raise ValueError("begin_task must run before propose")
        started = self.tasks[task]["version"]
        entry = {"type": "proposal", "task": task, "group": group, "base_version": started,
                 "built_on": self.latest, "proposal": proposal, "evidence": evidence}
        if self.frozen is not None:
            entry.update(decision="rejected", reason="frozen")
        elif proposal is None:
            entry.update(decision="rejected", reason="unparseable")
        else:
            try:
                parsed = P.RuleProposal.model_validate(proposal)
                if parsed.decision == "none":
                    entry.update(decision="deferred" if parsed.missing_facts else "none",
                                 reason="missing_extraction" if parsed.missing_facts else "")
                else:
                    current = self.load_version(self.latest)
                    candidate, rule, found = P.apply(current, parsed, task, answer)
                    result = verify(decision="modify" if parsed.decision == "revise" else "add",
                                    candidate=candidate, current=current, rule=rule,
                                    operation=P.operation_of(parsed, current), trigger=trigger,
                                    trigger_group=group, pool=pool)
                    entry.update(rule=rule, evidence_check=found,
                                 required_facts=next(c["required_facts"] for r in candidate["rules"]
                                                     if r["id"] == rule for c in r["constraints"]
                                                     if c.get("kind") == "template"), **result)
                    if result["decision"] == "accepted":
                        number = self.latest + 1
                        _write_json(self.versions / f"v{number:04d}.json", candidate)
                        entry.update(version=number, sha256=R.base_hash(candidate))
            except R.ProposalError as exc:
                entry.update(decision="rejected", reason=exc.code, detail=exc.detail)
            except ValueError as exc:  # pydantic validation of the model's JSON
                entry.update(decision="rejected", reason="invalid_proposal", detail=str(exc)[:500])
        _append(self.ledger_path, entry)
        self._replay()
        return entry

    def record_manual(self, note: str, *, task: str | None = None) -> None:
        _append(self.ledger_path, {"type": "manual", "task": task, "note": note})
        self._replay()

    def freeze(self) -> dict:
        if self.frozen is None:
            number = self.latest
            _append(self.ledger_path, {"type": "freeze", "version": number,
                                       "sha256": R.base_hash(self.load_version(number))})
            self._replay()
        return self.frozen

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for e in self.proposals.values():
            out[e["decision"]] = out.get(e["decision"], 0) + 1
        return out
