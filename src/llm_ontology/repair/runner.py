"""CLI of the C/D1/D2 repair-loop pilot (third runner; the matrices stay single-attempt).

    run_repair_loop.py --run-id X --mock                      # mechanism check, no model, no Java
    run_repair_loop.py --run-id X --build-pool                # labelled dev examples from stored outputs
    run_repair_loop.py --run-id X --check-public-checker      # L5 on stored outputs (RefactoringMiner)
    run_repair_loop.py --run-id X [--cases N|all]             # pilot with Qwen (Ollama)
    run_repair_loop.py --run-id X --freeze-d2                 # freeze the D2 base
    run_repair_loop.py --run-id X --report-only
    run_repair_loop.py --run-id Y --replay-d2-from X       # repeat only the D2 analysis on X's first answers
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from llm_ontology.repair import rules as R
from llm_ontology.repair.loop import FEEDBACK_VERSION, Loop, read_json, sha, write_json
from llm_ontology.repair.report import summarise
from llm_ontology.repair.verify import load_pool

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "configs/benchmarks/repair_loop_v1.json"
RUNS = REPO / "artifacts/evaluation/runs"


def _commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", default="refactoring", choices=["refactoring"])
    parser.add_argument("--cases", default="all")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--build-pool", action="store_true")
    parser.add_argument("--check-public-checker", action="store_true")
    parser.add_argument("--freeze-d2", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replay-d2-from", metavar="RUN_ID")
    parser.add_argument("--rules-d1", metavar="TTL", help="D1 base for the replay (default: the source run's v0); e.g. "
                        "configs/repair/rules_d1/refactoring.ttl")
    parser.add_argument("--catalogue", default="c1", choices=["c1", "c2"], help="D2 condition catalogue")
    parser.add_argument("--source-run", metavar="RUN_ID", help="selection.json of this run instead of the "
                        "configured matrix run (e.g. a development set)")
    parser.add_argument("--operation", help="operation of the matrix tasks (default: the configured pilot "
                        "operation); all-structural = every file-level task of the matrix")
    parser.add_argument("--reuse-first-attempt", action="store_true",
                        help="use the matrix onto_project answers as the shared first attempt (S@1 = that arm)")
    parser.add_argument("--feedback", default="repair-feedback-v1", choices=["repair-feedback-v1", "repair-feedback-v2"],
                        help="repair prompt text (same for C, D1 and D2)")
    parser.add_argument("--repair-temperature", type=float, default=0.0,
                        help="sampling temperature of repair attempts 2-3 (attempt 1 and analyses stay at 0)")
    parser.add_argument("--build-devset", type=int, metavar="N", help="development set: N tasks per stratum")
    parser.add_argument("--first-answers", action="store_true",
                        help="one first answer per task of --source-run, checked and scored, pilot run layout")
    parser.add_argument("--development-cases", action="store_true",
                        help="mark the replayed cases as development cases (they shaped the change)")
    parser.add_argument("--extrapolate-to", type=int, default=100)
    args = parser.parse_args(argv)

    config = read_json(CONFIG)
    root = RUNS / args.run_id
    d1_path = REPO / (args.rules_d1 or config["rules_d1"][args.task])
    d1 = R.load_d1(args.task, d1_path)
    if args.mock:
        from llm_ontology.repair.mock import mechanism
        fixtures = config["mechanism_fixtures"]
        task, provider, pool = mechanism(REPO / fixtures["cases"], REPO / fixtures["pool"])
        pool_path = REPO / config["mechanism_fixtures"]["pool"]
        source = None
    else:
        from llm_ontology.repair.refactoring_task import OllamaLoopProvider, RefactoringTask
        if args.build_devset:
            from llm_ontology.repair import devset
            dev = read_json(REPO / "configs/repair/devset_pv.json")
            info = devset.build(REPO, root, candidates_path=REPO / dev["candidates"],
                                pilot_selection=RUNS / config["source_runs"][args.task] / "selection.json",
                                matrix_root=RUNS / config["source_runs"][args.task],
                                per_stratum=args.build_devset, seed=dev["seed"])
            print(json.dumps({k: v for k, v in info.items() if k != "rejected"}), f"rejected={len(info['rejected'])}")
            return 0
        source = RUNS / (args.source_run or config["source_runs"][args.task])
        task = RefactoringTask(source, args.operation or config["pilot"][args.task]["operation"])
        if args.first_answers:
            from llm_ontology.repair import devset
            if root.resolve() != source.resolve():
                raise SystemExit("--first-answers writes into the development-set run: use --run-id = --source-run")
            provider = OllamaLoopProvider(context_window_tokens=config["context_window_tokens"], seed=config["seed"])
            rows = devset.first_answers(root, task, provider, repo=REPO, d1=d1,
                                        max_new_tokens=config["max_new_tokens"][args.task],
                                        analysis_tokens=config["analysis_max_new_tokens"])
            print(f"{len(rows)} first answers, {sum(r['public'] == 'PASSED' for r in rows)} pass the public checker, "
                  f"{sum(r['final_success'] for r in rows)} the final evaluator -> {root / 'first_answers.json'}")
            return 0
        pool_path = root / "dev_pool.json"
        provider, pool = None, []

    if args.replay_d2_from:
        from llm_ontology.repair.replay import replay
        if args.mock:
            from llm_ontology.repair.mock import ScriptedProvider, SCENARIO, scripted
            provider = ScriptedProvider(scripted(task.cases(), SCENARIO))
        else:
            provider = OllamaLoopProvider(context_window_tokens=config["context_window_tokens"], seed=config["seed"])
        if root.exists() and (root / "loop_plan.json").exists():
            raise SystemExit("Run ID belongs to a loop run; use a new run ID for the replay")
        rows = replay(RUNS / args.replay_d2_from, root, task, provider, analysis_tokens=config["analysis_max_new_tokens"],
                      catalogue=args.catalogue, d1=d1 if args.rules_d1 else None,
                      d1_name=args.rules_d1, development=args.development_cases)
        print(f"{sum(r.get('format', {}).get('valid', False) for r in rows)} formally valid of "
              f"{sum('skipped' not in r for r in rows)} -> {root / 'replay_report.md'}")
        return 0

    if args.build_pool or args.check_public_checker:
        root.mkdir(parents=True, exist_ok=True)
        if args.build_pool:
            manual = read_json(REPO / config["manual_labels"][args.task]).get("labels", {})
            rows = task.build_pool(config["pool_arms"], manual)
            write_json(pool_path, rows)
            print(f"{len(rows)} examples, {sum(r['defective'] for r in rows)} defective, "
                  f"{sum(r['label_source'] == 'manual' for r in rows)} manual -> {pool_path}")
        if args.check_public_checker:
            result = task.checker_agreement(config["pool_arms"], root / "public_checker")
            write_json(root / "public_checker.json", result)
            print(f"public checker: {result['outputs']} outputs, {len(result['disagreements'])} disagreements")
        return 0

    from llm_ontology.repair.refactoring_task import order
    cases = order(task.cases(), config["order_seed"])
    if args.cases != "all":
        cases = cases[:int(args.cases)]
    plan = {"protocol": config["protocol"], "run_id": args.run_id, "task": args.task, "mock": args.mock,
            "config_sha256": sha(CONFIG.read_text()), "commit": _commit(), "order_seed": config["order_seed"],
            "cases": [c["id"] for c in cases], "source_run": source.name if source else None,
            "d1_sha256": R.base_hash(d1), "pool_sha256": sha(pool_path.read_text()) if pool_path.exists() else None,
            "provider": "scripted-mock" if args.mock else "ollama:" + config["model"],
            "max_attempts": config["max_attempts"]}
    if args.operation:
        plan["operation"] = args.operation
    if args.repair_temperature:
        plan["repair_temperature"] = args.repair_temperature
    if args.reuse_first_attempt:
        plan["first_attempt"] = "matrix onto_project answers of " + source.name
    if args.feedback != FEEDBACK_VERSION:
        plan["feedback_version"] = args.feedback
    if args.rules_d1 or args.catalogue != "c1":  # absent for the defaults, so earlier plans stay comparable
        plan.update(rules_d1=args.rules_d1 or config["rules_d1"][args.task], catalogue=args.catalogue)
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0
    plan_path = root / "loop_plan.json"
    if plan_path.exists():
        old = read_json(plan_path)
        if {k: v for k, v in old.items() if k != "commit"} != {k: v for k, v in plan.items() if k != "commit"}:
            raise SystemExit("Plan changed; use a new run ID")
    else:
        write_json(plan_path, plan)
    if not args.mock:
        if not pool_path.exists():
            raise SystemExit("Run --build-pool first")
        pool = load_pool(pool_path)
        provider = OllamaLoopProvider(context_window_tokens=config["context_window_tokens"], seed=config["seed"])
    loop = Loop(root, task, provider, d1=d1, pool=pool, max_new_tokens=config["max_new_tokens"][args.task],
                analysis_tokens=config["analysis_max_new_tokens"], catalogue=args.catalogue,
                first_attempt_from=source if args.reuse_first_attempt else None,
                repair_temperature=args.repair_temperature, feedback_style=args.feedback)
    if args.freeze_d2:
        print(json.dumps(loop.state.freeze()))
        return 0
    if not args.report_only:
        loop.run(cases)
    table = loop.score(cases)
    summary = summarise(root, table, cases, extrapolate_to=args.extrapolate_to)
    print(json.dumps(summary["success"]), "->", root / "loop_report.md")
    return 0
