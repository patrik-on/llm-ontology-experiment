"""Repeat only the D2 analysis on stored first answers, with the current analysis prompt.

Reads a finished pilot run (its shared first answers, D2 check results and rule reports, the
D2 version each task started with, ``dev_pool.json``) and writes a new run directory. The pilot
run and its rule base are never changed; candidate verification runs on a copy in memory and
is informational. Factual correctness is "unverified" until ``manual_review.json`` is filled in.
"""
from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.repair import proposal as P
from llm_ontology.repair import rules as R
from llm_ontology.repair.loop import Check, analysis_prompt, d2_schema, numbered, read_json, sha, write_json
from llm_ontology.repair.verify import load_pool, verify

REVIEW_FIELDS = {"diagnosis_fits": None, "condition_fits_error": None, "note": ""}


def _source(task, case, raw):
    try:
        return task.source(case, raw)
    except Exception:
        return None


def validate(payload, base: dict, answer: str | None) -> dict:
    """Format validation only: schema model, catalogue values, evidence in the answer."""
    if not isinstance(payload, dict):
        return {"valid": False, "reason": "missing_rule_proposal"}
    try:
        parsed = P.RuleProposal.model_validate(payload)
    except ValueError as exc:
        return {"valid": False, "reason": "invalid_proposal", "detail": str(exc)[:300]}
    if parsed.decision == "none":
        return {"valid": bool(parsed.reason.strip()), "reason": "" if parsed.reason.strip() else "missing_reason",
                "decision": "none"}
    try:
        constraint, evidence = P.to_constraint(parsed, base, answer)
    except R.ProposalError as exc:
        return {"valid": False, "reason": exc.code, "detail": exc.detail, "decision": parsed.decision}
    return {"valid": True, "reason": "", "decision": parsed.decision, "evidence_check": evidence,
            "required_facts": constraint["required_facts"]}


def replay(source_root: Path, out_root: Path, task, provider, *, analysis_tokens: int) -> list[dict]:
    source_root, out_root = Path(source_root), Path(out_root)
    ledger = [json.loads(x) for x in (source_root / "rulebase_d2/ledger.jsonl").read_text().splitlines() if x]
    starts = {e["task"]: e["version"] for e in ledger if e["type"] == "task_start"}
    originals = {e["task"]: e for e in ledger if e["type"] == "proposal"}
    pool_path = source_root / "dev_pool.json"
    pool = load_pool(pool_path) if pool_path.exists() else []
    cases = {c["id"]: c for c in task.cases()}
    plan = read_json(source_root / "loop_plan.json")
    write_json(out_root / "replay_plan.json", {"source_run": source_root.name, "prompt_version": P.PROMPT_VERSION,
                                               "cases": plan["cases"], "analysis_tokens": analysis_tokens,
                                               "provider": getattr(provider, "name", "?")})
    review_path = out_root / "manual_review.json"
    review = read_json(review_path) if review_path.exists() else {}
    rows = []
    for cid in plan["cases"]:
        case, sroot, out = cases[cid], source_root / "cases" / cid, out_root / "cases" / cid
        raw = (sroot / "shared/attempt-1/raw.txt").read_text(encoding="utf-8")
        prompt1 = (sroot / "shared/attempt-1/prompt.txt").read_text(encoding="utf-8")
        stored = read_json(sroot / "D2/attempt-1/check.json")
        source = _source(task, case, raw)
        check = Check(stored["status"], stored["success"], stored["repairable"], stored["tool"], stored["messages"],
                      source)
        if check.success:
            rows.append({"case": cid, "skipped": "first attempt passed"})
            continue
        rules_json = read_json(sroot / "D2/attempt-1/rules.json")
        reports = [r["message"] for r in rules_json["findings"] if r["severity"] == "Violation"]
        base = read_json(source_root / f"rulebase_d2/versions/v{starts.get(cid, 0):04d}.json")
        if R.base_hash(base) != rules_json["base_sha256"]:
            raise ValueError("Stored rule reports were not made with the recorded D2 version: " + cid)
        prompt = analysis_prompt("D2", prompt1, raw, check, reports, base, task.kind)
        out.mkdir(parents=True, exist_ok=True)
        if (out / "raw.txt").exists() and (out / "prompt.txt").read_text(encoding="utf-8") == prompt:
            text = (out / "raw.txt").read_text(encoding="utf-8")
        else:
            (out / "prompt.txt").write_text(prompt, encoding="utf-8")
            gen = provider.generate(prompt, d2_schema(base), analysis_tokens)
            text = gen.text
            (out / "raw.txt").write_text(text, encoding="utf-8")
            write_json(out / "generation.json", {"prompt_sha256": sha(prompt), "prompt_tokens": gen.prompt_tokens,
                                                 "output_tokens": gen.output_tokens, "seconds": gen.seconds})
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {}
        new = payload.get("rule_proposal") if isinstance(payload, dict) else None
        old_raw = sroot / "D2/analysis/raw.txt"
        old = json.loads(old_raw.read_text()).get("rule_proposal") if old_raw.exists() else None
        result = validate(new, base, source)
        info = None
        if result["valid"] and result["decision"] != "none":
            parsed = P.RuleProposal.model_validate(new)
            candidate, rule, _ = P.apply(base, parsed, "replay:" + cid, source)
            trigger = task.facts(case, source) if source else None
            info = verify(decision="modify" if parsed.decision == "revise" else "add", candidate=candidate,
                          current=base, rule=rule, operation=P.operation_of(parsed, base), trigger=trigger,
                          trigger_group=task.group(case), pool=pool)
            info = {"decision": info["decision"], "reason": info["reason"],
                    "added_coverage": info["checks"].get("added_coverage"),
                    "new_false_positives": info["checks"].get("new_false_positives")}
        row = {"case": cid, "status": check.status, "rule_reports": reports,
               "original": {"proposal": old, "decision": originals.get(cid, {}).get("decision"),
                            "reason": originals.get(cid, {}).get("reason")},
               "new": new, "diagnosis": {k: payload.get(k) for k in ("location", "cause")} if isinstance(payload, dict) else {},
               "format": result, "verification_info": info,
               "review": review.get(cid, dict(REVIEW_FIELDS))}
        write_json(out / "result.json", row)
        (out / "review.md").write_text(_review_md(case, check, reports, row), encoding="utf-8")
        rows.append(row)
    if not review_path.exists():
        write_json(review_path, {r["case"]: dict(REVIEW_FIELDS) for r in rows if "skipped" not in r})
    (out_root / "replay_report.md").write_text(report_md(rows, source_root.name), encoding="utf-8")
    write_json(out_root / "replay_summary.json", rows)
    return rows


def _review_md(case, check, reports, row) -> str:
    new = row["new"] or {}
    ev = (new.get("evidence") or {}) if isinstance(new, dict) else {}
    return "\n".join([
        f"# {case['id']}", "", "Request: " + case["request"], "", f"Status: {check.status}", "Tool output:",
        *["- " + m for m in check.messages], "Rule reports (active base):", *(["- " + m for m in reports] or ["- (none)"]),
        "", "## Diagnosis (model)", f"Location: {row['diagnosis'].get('location')}",
        f"Cause: {row['diagnosis'].get('cause')}", "", "## New proposal", "```json",
        json.dumps(new, indent=2, ensure_ascii=False), "```", f"Quoted snippet: `{ev.get('snippet')}` (line {ev.get('line')})",
        f"Format: {json.dumps(row['format'], ensure_ascii=False)}", "", "## Original proposal", "```json",
        json.dumps(row["original"], indent=2, ensure_ascii=False), "```", "",
        "## Answer (numbered)", "```java", numbered(check.source), "```", "",
        "Manual review: fill `manual_review.json` (diagnosis_fits, condition_fits_error: true/false, note)."])


def report_md(rows: list[dict], source: str) -> str:
    done = [r for r in rows if "skipped" not in r]
    lines = [f"# Skúška rozboru D2 na uložených prvých odpovediach ({source})", "",
             f"Verzia promptu: `{P.PROMPT_VERSION}`. Báza: verzia, s ktorou úloha v pilote začala (nezmenená).", "",
             "| Prípad | pôvodne | nový návrh | podmienka / pravidlo | úryvok nájdený | formát | overenie (info) | vecne |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "skipped" in r:
            lines.append(f"| `{r['case'][-8:]}` | – | – | – | – | – | – | {r['skipped']} |")
            continue
        new = r["new"] if isinstance(r["new"], dict) else {}
        fmt = r["format"]
        ev = fmt.get("evidence_check")
        vec = r["review"].get("condition_fits_error")
        lines.append(" | ".join([
            f"| `{r['case'][-8:]}`", f"{r['original']['decision']} ({r['original']['reason'] or '–'})",
            str(new.get("decision")), f"{new.get('must_hold') or '–'} / {new.get('target_rule') or '–'}",
            "áno" if ev else ("nie" if fmt.get("reason", "").startswith("evidence") else "–"),
            "platný" if fmt["valid"] else f"neplatný ({fmt['reason']})",
            (r["verification_info"] or {}).get("decision", "–") if r["verification_info"] else "–",
            "neoverené" if vec is None else ("áno" if vec else "nie")]) + " |")
    valid = sum(r["format"]["valid"] for r in done)
    fits = [r for r in done if r["review"].get("condition_fits_error") is not None]
    lines += ["", f"Formálne platných návrhov: {valid} z {len(done)}. "
              f"Vecne posúdených: {len(fits)}, z toho vystihlo skutočnú chybu: "
              f"{sum(bool(r['review']['condition_fits_error']) for r in fits)}"
              + (" (bez ručného posúdenia je vecná správnosť neoverená)." if not fits else "."), ""]
    return "\n".join(lines)
