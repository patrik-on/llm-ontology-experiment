"""Generate project-ontology blocks for every refactoring cohort case and report on them.

Writes ``report.json`` (per-case status, block length, failures) and ``samples.md`` (blocks for a
fixed, stratified sample to check by hand for factual correctness). No model calls.
Token counts use ``--tokenizer`` (a local HF tokenizer path); without it they are a character
estimate and labelled as such.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology import ontology  # noqa: E402

BASE_FACTS = ("Target lines", "Fields of", "Methods of", "Names already declared")
CHARS_PER_TOKEN = 3.2  # rough estimate for code-like English text, only without a tokenizer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/validation/refactoring_mixed_v1/manifest.json")
    parser.add_argument("--out", default="artifacts/ontology/cohort-check")
    parser.add_argument("--tokenizer", default=None)
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()

    count = None
    if args.tokenizer:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True, local_files_only=True)
        def count(text):
            return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    cases = json.loads((ROOT / args.manifest).read_text(encoding="utf-8"))["cases"]
    rows, blocks = [], {}
    for case in cases:
        row = {"id": case["id"], "source": case["source"], "operation": case["operation"]}
        try:
            block, identity = ontology.refactoring_context(case)
        except Exception as exc:  # report every failure; nothing is retried or repaired
            row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        else:
            facts = block.splitlines()[1:-1]
            specific = [f for f in facts if not f.startswith(BASE_FACTS)]
            row.update(status="ok", facts=len(facts), chars=len(block), block_sha256=identity["block_sha256"],
                       tokens=count(block) if count else round(len(block) / CHARS_PER_TOKEN),
                       operation_specific=bool(specific))
            blocks[case["id"]] = block
        rows.append(row)

    ok = [r for r in rows if r["status"] == "ok"]
    tokens = sorted(r["tokens"] for r in ok)
    summary = {
        "cases": len(rows), "ok": len(ok), "failed": len(rows) - len(ok),
        "token_count": "tokenizer" if count else f"estimate (chars / {CHARS_PER_TOKEN})",
        "tokens_median": statistics.median(tokens) if tokens else None,
        "tokens_p95": tokens[int(0.95 * (len(tokens) - 1))] if tokens else None,
        "tokens_max": tokens[-1] if tokens else None,
        "without_operation_specific_facts": sum(not r["operation_specific"] for r in ok),
        "by_operation": dict(Counter(r["operation"] for r in rows)),
        "failures": [r for r in rows if r["status"] == "failed"],
    }
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps({"summary": summary, "cases": rows}, indent=2) + "\n")

    # One sample per operation first (stable id order), then fill up to --samples.
    picked, seen = [], set()
    for r in sorted(ok, key=lambda r: r["id"]):
        if r["operation"] not in seen:
            picked.append(r)
            seen.add(r["operation"])
    picked += [r for r in sorted(ok, key=lambda r: r["id"]) if r not in picked][: max(0, args.samples - len(picked))]
    by_id = {c["id"]: c for c in cases}
    lines = ["# Ontology blocks: samples for manual fact check", ""]
    for r in picked:
        case = by_id[r["id"]]
        lines += [f"## {r['id']} ({r['operation']}, {r['source']})", "",
                  f"Request: {case.get('request') or case['target'].get('method', '')}", f"Target lines: {case['target']['start']}..{case['target']['end']}",
                  "", "```", blocks[r["id"]], "```", ""]
    (out / "samples.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
