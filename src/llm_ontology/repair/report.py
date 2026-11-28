"""Summary and Markdown report of a repair-loop run (reads only the run directory)."""
from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.benchmarks.paired_tests import mcnemar_exact
from llm_ontology.repair.loop import MAX_ATTEMPTS, VARIANTS, read_json, write_json


def _calls(root: Path) -> list[dict]:
    path = root / "calls.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines() if x] if path.exists() else []


def _violations(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(r["message"] for r in read_json(path)["findings"] if r["severity"] == "Violation")


def pair(table: dict, a: str, b: str, key: str = f"S@{MAX_ATTEMPTS}") -> dict:
    rows = [(r[a][key], r[b][key], cid) for cid, r in table.items() if a in r and b in r]
    both = sum(x and y for x, y, _ in rows)
    a_only = [c for x, y, c in rows if x and not y]
    b_only = [c for x, y, c in rows if y and not x]
    n = len(rows)
    return {"pair": f"{a} vs {b}", "n": n, "both": both, "a_only": a_only, "b_only": b_only,
            "neither": n - both - len(a_only) - len(b_only),
            "delta_pp": (100.0 * (len(a_only) - len(b_only)) / n) if n else None,
            "mcnemar": mcnemar_exact(len(a_only), len(b_only)), "interpretation": "descriptive (pilot)"}


def summarise(root: Path, table: dict, cases: list[dict], *, extrapolate_to: int = 100) -> dict:
    root = Path(root)
    calls = _calls(root)
    variants = [v for v in VARIANTS if any(v in r for r in table.values())]
    n = len(table)
    success = {v: {f"S@{k}": sum(r[v][f"S@{k}"] for r in table.values() if v in r) for k in range(1, MAX_ATTEMPTS + 1)}
               for v in variants}
    shared = [c for c in calls if c["variant"] == "shared"]
    costs = {}
    for v in variants:
        own = [c for c in calls if c["variant"] == v]
        rule_seconds = sum(read_json(p).get("seconds", 0) for p in root.glob(f"cases/*/{v}/attempt-*/rules.json"))
        costs[v] = {"calls_generate": sum(c["kind"] == "generate" for c in own) + len(shared),
                    "calls_analysis": sum(c["kind"] == "analysis" for c in own),
                    "prompt_tokens": sum((c["prompt_tokens"] or 0) for c in own + shared),
                    "output_tokens": sum((c["output_tokens"] or 0) for c in own + shared),
                    "generation_seconds": sum(c["seconds"] for c in own + shared),
                    "rule_check_seconds": rule_seconds}
    ledger = root / "rulebase_d2" / "ledger.jsonl"
    entries = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
    proposals = [e for e in entries if e["type"] == "proposal"]
    decisions: dict[str, int] = {}
    for e in proposals:
        decisions[e["decision"]] = decisions.get(e["decision"], 0) + 1
    if "D2" in costs:
        costs["D2"]["verification_seconds"] = sum(e.get("seconds", 0) for e in proposals)
    starts = {e["task"]: e for e in entries if e["type"] == "task_start"}
    order = [c["id"] for c in cases if c["id"] in table]
    accepted = []
    for e in (p for p in proposals if p["decision"] == "accepted"):
        later = [cid for cid in order if starts.get(cid, {}).get("version", 0) >= e["version"]
                 and starts[cid]["group"] != e["group"]]
        changed = [cid for cid in later
                   if _violations(root / "cases" / cid / "D2/attempt-1/rules.json")
                   != _violations(root / "cases" / cid / "D1/attempt-1/rules.json")]
        accepted.append({"task": e["task"], "rule": e["rule"], "version": e["version"],
                         "added_coverage": e["checks"].get("added_coverage"), "later_distinct_tasks": len(later),
                         "report_changed_vs_d1": changed,
                         "report_changed_and_d2_passed": [c for c in changed if table[c]["D2"][f"S@{MAX_ATTEMPTS}"]],
                         "report_changed_and_d1_passed": [c for c in changed if table[c]["D1"][f"S@{MAX_ATTEMPTS}"]]})
    example = None
    for cid in order:
        f1, f2 = (root / "cases" / cid / v / "attempt-2/feedback.txt" for v in ("D1", "D2"))
        differ = (_violations(root / "cases" / cid / "D1/attempt-1/rules.json")
                  != _violations(root / "cases" / cid / "D2/attempt-1/rules.json"))
        if f1.exists() and f2.exists() and differ:
            example = {"case": cid, "D1_feedback": f1.read_text(), "D2_feedback": f2.read_text(),
                       "D1_S@3": table[cid]["D1"]["S@3"], "D2_S@3": table[cid]["D2"]["S@3"]}
            break
    per_task_calls = (len(calls) / n) if n else 0
    per_task_seconds = (sum(c["seconds"] for c in calls) / n) if n else 0
    frozen = next((e for e in entries if e["type"] == "freeze"), None)
    ops = sorted({c.get("operation", "?") for c in cases if c["id"] in table})
    by_operation = {op: {"n": sum(c.get("operation") == op for c in cases if c["id"] in table),
                         **{v: sum(table[c["id"]][v][f"S@{MAX_ATTEMPTS}"] for c in cases
                                   if c["id"] in table and c.get("operation") == op and v in table[c["id"]])
                            for v in variants}} for op in ops}
    repeats = {}
    for v in variants:
        rows = [read_json(p) for p in root.glob(f"cases/*/{v}/completion.json")]
        att = [a for r in rows for a in r["attempts"] if a["attempt"] > 1]
        repeats[v] = {"repair_attempts": len(att), "repeated": sum(a.get("repeats_attempt") is not None for a in att)}
    plan = read_json(root / "loop_plan.json")
    matrix_check = None
    if plan.get("first_attempt") and plan.get("source_run"):
        mroot = root.parent / plan["source_run"] / "cases"
        diff = [cid for cid in order if (mroot / cid / "predictions/onto_project/evaluation/evaluation.json").exists()
                and bool(read_json(mroot / cid / "predictions/onto_project/evaluation/evaluation.json")
                         .get("structural_success")) != bool(table[cid][variants[0]]["S@1"])]
        matrix_check = {"compared": len(order), "differs": diff}
    summary = {"cases": n, "success": success, "status": {v: _status(table, v) for v in variants},
               "pairs": [pair(table, "D1", "C"), pair(table, "D2", "D1")] if {"C", "D1", "D2"} <= set(variants) else [],
               "costs": costs, "proposals": decisions, "accepted": accepted, "example": example,
               "d2_final_version": max([0] + [e.get("version", 0) for e in proposals if e["decision"] == "accepted"]),
               "d2_frozen": frozen, "by_operation": by_operation, "repeats": repeats, "matrix_check": matrix_check,
               "extrapolation": {"tasks": extrapolate_to, "calls": round(per_task_calls * extrapolate_to),
                                 "generation_hours": round(per_task_seconds * extrapolate_to / 3600, 2),
                                 "note": "model calls only; checker, scorer and rule time are listed per variant"}}
    write_json(root / "loop_summary.json", summary)
    (root / "loop_report.md").write_text(markdown(summary, read_json(root / "loop_plan.json")), encoding="utf-8")
    return summary


def _status(table, v):
    out: dict[str, int] = {}
    for r in table.values():
        if v in r:
            out[r[v]["status"]] = out.get(r[v]["status"], 0) + 1
    return out


def markdown(s: dict, plan: dict) -> str:
    kind = "SKÚŠKA MECHANIZMU (náhradný model, nie výsledky Qwenu)" if plan.get("mock") else "beh s modelom"
    lines = [f"# Slučka C/D1/D2: {plan['run_id']}", "", f"Druh behu: **{kind}**. Model: `{plan['provider']}`. "
             f"Úloha: {plan['task']}, prípady: {s['cases']}, poradie: `{plan['order_seed']}`.", "",
             "## Úspešnosť (konečný hodnotiteľ)", "", "| Variant | S@1 | S@2 | S@3 | stavy |", "|---|---:|---:|---:|---|"]
    for v, row in s["success"].items():
        lines.append(f"| {v} | {row['S@1']} | {row['S@2']} | {row['S@3']} | {json.dumps(s['status'][v])} |")
    if s.get("matrix_check"):
        m = s["matrix_check"]
        lines += ["", f"S@1 oproti matici (`onto_project`, rovnaká odpoveď): zhoda {m['compared'] - len(m['differs'])} z "
                  f"{m['compared']}" + (f"; odlišné: {', '.join(m['differs'])}" if m["differs"] else "") + "."]
    if s.get("by_operation") and len(s["by_operation"]) > 1:
        vs = list(s["success"])
        lines += ["", "## Podľa operácie (S@3)", "", "| Operácia | n | " + " | ".join(vs) + " |",
                  "|---|---:|" + "---:|" * len(vs)]
        for op, row in s["by_operation"].items():
            lines.append(f"| {op} | {row['n']} | " + " | ".join(str(row[v]) for v in vs) + " |")
    if s.get("repeats"):
        lines += ["", "Opravné pokusy zhodné s predchádzajúcou odpoveďou: " + ", ".join(
            f"{v} {r['repeated']}/{r['repair_attempts']}" for v, r in s["repeats"].items()) + "."]
    lines += ["", "## Párové porovnania pri S@3 (opisne)", "", "| Pár | n | oba | iba prvý | iba druhý | ani jeden | Δ p.b. | McNemar p |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for p in s["pairs"]:
        lines.append(f"| {p['pair']} | {p['n']} | {p['both']} | {len(p['a_only'])} | {len(p['b_only'])} | {p['neither']} | "
                     f"{p['delta_pp']:+.1f} | {p['mcnemar']['p_value']} |")
    lines += ["", "## Náklady", "", "| Variant | volania gen. | volania rozbor | tokeny vstup | tokeny výstup | čas gen. (s) | čas pravidiel (s) | čas overenia (s) |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for v, c in s["costs"].items():
        lines.append(f"| {v} | {c['calls_generate']} | {c['calls_analysis']} | {c['prompt_tokens']} | {c['output_tokens']} | "
                     f"{c['generation_seconds']:.1f} | {c['rule_check_seconds']:.1f} | {c.get('verification_seconds', 0):.1f} |")
    lines += ["", "Spoločný prvý pokus je v každom variante započítaný celý (vznikol raz na úlohu).", "",
              f"Odhad pre {s['extrapolation']['tasks']} úloh: {s['extrapolation']['calls']} volaní modelu (C, D1 a D2 spolu), "
              f"{s['extrapolation']['generation_hours']} h generovania.", "",
              "## Čo pridala AI (D2)", "", f"Návrhy podľa rozhodnutia: {json.dumps(s['proposals'])}. "
              f"Konečná verzia: v{s['d2_final_version']}; zmrazená: {'áno' if s['d2_frozen'] else 'nie'}.", ""]
    for a in s["accepted"]:
        lines.append(f"- úloha `{a['task']}` → pravidlo {a['rule']} (v{a['version']}): neskorších odlišných úloh "
                     f"{a['later_distinct_tasks']}, hlásenie iné ako v D1: {len(a['report_changed_vs_d1'])}, "
                     f"z toho D2 úspešné: {len(a['report_changed_and_d2_passed'])}, D1 úspešné: "
                     f"{len(a['report_changed_and_d1_passed'])}.")
    if s["example"]:
        e = s["example"]
        lines += ["", f"## Jedna chyba, dve opravné vetvy (`{e['case']}`)", "",
                  f"Rovnaká prvá odpoveď. D1 S@3 = {e['D1_S@3']}, D2 S@3 = {e['D2_S@3']}.", "", "D1:", "", "```",
                  e["D1_feedback"], "```", "", "D2:", "", "```", e["D2_feedback"], "```"]
    return "\n".join(lines) + "\n"
