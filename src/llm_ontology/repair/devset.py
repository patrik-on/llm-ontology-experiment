"""Development set of further Parameterize Variable tasks for the D2 analysis (no pilot tasks).

``build`` picks tasks from the reference-screened candidates of an earlier preparation run in a
fixed order (sha256(seed + id)), skips the pilot's task IDs and commits, balances two strata
(the requested method is / is not declared in the input) and runs the same reference QA as the
matrix (``structural_qa``: reference accepted, no-op, invalid Java and wrong target rejected).
It writes ``selection.json`` in the matrix format, so ``RefactoringTask`` reads it unchanged.

``first_answers`` generates one first answer per task with the pilot's first-attempt prompt,
checks it with the public checker, computes the D1 rule reports, scores it with the final
evaluator and lays the run out like a pilot run (``shared/attempt-1``, ``D2/attempt-1``,
``rulebase_d2``), so ``--replay-d2-from`` can repeat the D2 analysis on it. ``dev_pool.json``
holds the first answers (label: final evaluator) and the reference solutions (label: correct);
both carry gold information and are development data only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from llm_ontology.repair import rules as R
from llm_ontology.repair.java_facts import _Unit, parse_request
from llm_ontology.repair.loop import Loop, read_json, sha, write_json


def requested_method_in_input(case: dict) -> bool:
    req = parse_request(case["request"])
    unit = _Unit(case["before"])
    return any(unit.name(m) == req.method for m in unit.methods())


def build(repo: Path, root: Path, *, candidates_path: Path, pilot_selection: Path, matrix_root: Path,
          per_stratum: int, seed: str, operation: str = "Parameterize Variable") -> dict:
    from llm_ontology.benchmarks import refactoring_execution as ex
    from llm_ontology.benchmarks import refactoring_matrix as M
    from llm_ontology.benchmarks.refactoring_cohort import structural_qa

    root.mkdir(parents=True, exist_ok=True)
    pilot = read_json(pilot_selection)
    used_ids = {c["id"] for c in pilot["cases"]}
    used_commits = {c["commit"] for c in pilot["cases"]}
    pool = [c for c in read_json(candidates_path) if c["operation"] == operation]
    eligible = [c for c in pool if c["id"] not in used_ids and c["commit"] not in used_commits]
    ordered = sorted(eligible, key=lambda c: hashlib.sha256((seed + c["id"]).encode()).hexdigest())
    validate = M.prompt_screen(matrix_root, read_json(matrix_root / "matrix_plan.json"))
    tool = pilot["tool"]
    accepted, rejected, taken = [], [], {True: 0, False: 0}
    for case in ordered:
        stratum = requested_method_in_input(case)
        if taken[stratum] >= per_stratum:
            continue
        out = root / "preparation" / case["id"]
        try:
            gold = ex.read_utf8(Path(case["reference_path"]))
            if (out / "qa/qa.json").exists():
                control = read_json(out / "qa/qa.json")
            else:
                control = structural_qa(case, gold, out / "qa", tool, validate)
            if not control["passed"]:
                raise ValueError("reference or negative controls failed: " + json.dumps(control["checks"]))
            write_json(out / "reference-private.json", {"source": gold})
            public = {k: v for k, v in case.items() if k != "reference_path"}
            public.update(reference_private=str((out / "reference-private.json").relative_to(repo)),
                          qa_path=str((out / "qa/qa.json").relative_to(repo)), devset_stratum=
                          "method_in_input" if stratum else "method_not_in_input")
            accepted.append(public)
            taken[stratum] += 1
        except Exception as exc:
            rejected.append({"id": case["id"], "reason": str(exc)[:300]})
        if all(n >= per_stratum for n in taken.values()):
            break
    selection = {"tool": tool, "cases": accepted, "devset": {
        "seed": seed, "operation": operation, "per_stratum": per_stratum,
        "candidates": str(candidates_path.relative_to(repo)), "candidates_sha256": ex.file_sha256(candidates_path),
        "eligible": len(eligible), "excluded_pilot_ids": len([c for c in pool if c["id"] in used_ids]),
        "excluded_pilot_commits": len([c for c in pool if c["id"] not in used_ids and c["commit"] in used_commits]),
        "rejected": rejected, "strata": {"method_in_input": taken[True], "method_not_in_input": taken[False]},
        "pilot_projects": sorted({c["provenance"]["archive"].rsplit("/", 1)[-1] for c in pilot["cases"]
                                  if c["operation"] == operation}),
        "model_calls": 0}}
    write_json(root / "selection.json", selection)
    return selection["devset"]


def first_answers(root: Path, task, provider, *, repo: Path, d1: dict, max_new_tokens: int, analysis_tokens: int) -> list[dict]:
    """One first answer per task, laid out like a pilot run (see module docstring)."""
    root = Path(root)
    loop = Loop(root, task, provider, d1=d1, pool=[], max_new_tokens=max_new_tokens,
                analysis_tokens=analysis_tokens, variants=("D2",))
    cases = task.cases()
    plan = {"protocol": "repair_devset_first_answers_v1", "cases": [c["id"] for c in cases],
            "d1_sha256": R.base_hash(d1), "provider": getattr(provider, "name", "?")}
    if (root / "loop_plan.json").exists() and read_json(root / "loop_plan.json") != plan:
        raise SystemExit("Plan changed; use a new run ID")
    write_json(root / "loop_plan.json", plan)
    rows, pool = [], []
    for case in cases:
        cid = case["id"]
        croot = root / "cases" / cid
        prompt1 = task.prompt(case)
        raw = loop._call(croot / "shared" / "attempt-1", prompt1, task.schema(), max_new_tokens,
                         kind="generate", case=cid, variant="shared", attempt=1)
        adir = croot / "D2" / "attempt-1"
        adir.mkdir(parents=True, exist_ok=True)
        if (adir / "check.json").exists():
            stored = read_json(adir / "check.json")
        else:
            check = task.check(case, raw, adir / "check")
            stored = {**check.__dict__, "source": None}
            write_json(adir / "check.json", stored)
        try:
            source = task.source(case, raw)
        except Exception:
            source = None
        loop.state.begin_task(cid, task.group(case))
        if not (adir / "rules.json").exists():
            from llm_ontology.repair.loop import Check
            loop._reports(case, Check(stored["status"], stored["success"], stored["repairable"], stored["tool"],
                                      stored["messages"], source), d1, adir)
        score_path = croot / "scores.json"
        scores = read_json(score_path) if score_path.exists() else {}
        if sha(raw) not in scores:
            scores[sha(raw)] = task.score(case, raw, croot / "final" / sha(raw)[:16])
            write_json(score_path, scores)
        final = bool(scores[sha(raw)]["success"])
        rows.append({"case": cid, "stratum": case.get("devset_stratum"), "public": stored["status"],
                     "final_success": final})
        common = {"group": cid, "task": "refactoring", "operation": case["operation"], "before": case["before"],
                  "request": case["request"], "note": "",
                  "target_start": int(case["target"]["start"] if "target" in case else case["target_start"])}
        if source is not None:
            pool.append({**common, "id": f"{cid}/first", "after": source, "defective": not final,
                         "label_source": "final_evaluator"})
        reference = (json.loads((Path(repo) / case["reference_private"]).read_text(encoding="utf-8"))["source"]
                     if "reference_private" in case else case["expected"])  # synthetic cases carry it inline
        pool.append({**common, "id": f"{cid}/reference", "after": reference, "defective": False,
                     "label_source": "reference"})
    write_json(root / "dev_pool.json", pool)
    write_json(root / "first_answers.json", rows)
    return rows
