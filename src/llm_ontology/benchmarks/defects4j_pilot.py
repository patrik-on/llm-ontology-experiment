"""Opt-in three-real-case composition; no retries, repairs, audit or index writes."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path

from llm_ontology.benchmarks.defects4j import (
    Defects4JConfig, load_config, prepare, require_wsl, verify_prepared,
)
from llm_ontology.benchmarks.defects4j_execution import (
    evaluate_pair, evaluate_revision, file_sha256, write_json,
)
from llm_ontology.benchmarks.defects4j_runner import (
    ARMS, build_dependency_identity, generate_ft, generate_rag,
    generation_failure_payload, hf_identity, load_eval_model,
)
from llm_ontology.benchmarks.testing_format_validation import generation_observation
from llm_ontology.core.config import read_yaml
from llm_ontology.evaluation.run_layout import (
    require_canonical_evaluation_path, validate_evaluation_run_id,
)
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting.testing_full_class_v2 import apply_profile, profile_identity

PROTOCOL = "defects4j_three_case_full_class_v2"
DEFAULT_CONFIG = Path("configs/benchmarks/defects4j_three_case_full_class_v2.yaml")
# Model-free build/launcher canary, not a gold fault oracle. Never forwarded to models.
HEALTH = '''import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;
public class BuildHealth { @Test void productionLoads() throws Exception {
    assertTrue(Class.forName("%s").getName().equals("%s"));
} }'''


def load_protocol(path: Path) -> tuple[dict, list[Defects4JConfig]]:
    raw = read_yaml(path)
    if (raw["protocol"] != PROTOCOL or raw["prompt_profile"] != "testing-full-class-v2"
            or raw["max_new_tokens"] != 4096 or raw["max_generation_calls"] != 9
            or len(raw["cases"]) != 3):
        raise ValueError("Exactly three real cases, v2 profile, 4096 tokens and nine calls required.")
    base = load_config(Path(raw["runtime_config"]))
    configs = [Defects4JConfig.model_validate({**base.model_dump(), **case,
               "prompt_profile": raw["prompt_profile"], "max_new_tokens": 4096})
               for case in raw["cases"]]
    if len({c.case_id for c in configs}) != 3:
        raise ValueError("Cases must be distinct.")
    return raw, configs


def identity(path: Path, raw: dict, configs: list[Defects4JConfig]) -> dict:
    c = configs[0]
    return {"protocol": PROTOCOL, "config_sha256": file_sha256(path),
            "runtime_config_sha256": file_sha256(Path(raw["runtime_config"])),
            "sources": build_dependency_identity(c), "profile": profile_identity(),
            "configs": [x.model_dump(mode="json") for x in configs],
            "java": file_sha256(c.java_home / "bin/java"),
            "javac": file_sha256(c.java_home / "bin/javac"),
            "junit": file_sha256(c.junit_jar)}


def verify(root: Path, pins: dict, configs: list[Defects4JConfig]) -> dict:
    frozen = json.loads((root / "freeze.json").read_text())
    if frozen["identity"] != pins:
        raise ValueError("Frozen source/config identity changed; do not resume generation.")
    for c in configs:
        case_root = root / "cases" / c.case_id
        p = case_root / "prepared.json"
        if file_sha256(p) != frozen["prepared"][c.case_id]:
            raise ValueError("Prepared case changed.")
        verify_prepared(json.loads(p.read_text()), c, prepared_path=p)
        for arm in ARMS:
            case = case_root / "prompts" / f"{arm}.json"
            if file_sha256(case) != frozen["case_profiles"][c.case_id][arm]:
                raise ValueError("Frozen case profile changed.")
    return frozen


def attempt(root: Path, c: Defects4JConfig, arm: str) -> Path:
    # Atomic exclusive cell reservation counts even failure/interruption; no retry route.
    out = root / "cases" / c.case_id / "predictions" / arm
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "attempt.json", {"case_id": c.case_id, "arm": arm, "attempt": 1,
               "charged_to_budget": True, "max_generation_calls": 9})
    if len(list(root.glob("cases/*/predictions/*/attempt.json"))) > 9:
        raise RuntimeError("Generation budget exceeded.")
    return out


def generate_cell(root: Path, c: Defects4JConfig, arm: str, loaded=None, model_id=None):
    out = attempt(root, c, arm)
    case_root = root / "cases" / c.case_id
    case = ExperimentCase.model_validate_json((case_root / "prompts" / f"{arm}.json").read_text())
    try:
        generated = (generate_ft(c, case, out, loaded_model=loaded, model_identity=model_id)
                     if arm == "ft_testing" else generate_rag(c, case, out, arm,
                     {"audit_status": "deferred_by_user", "exploratory": True}))
        (out / "generated.java").write_text(generated["source"], encoding="utf-8")
        generated.update({"source_sha256": file_sha256(out / "generated.java"), "protocol": PROTOCOL})
        write_json(out / "generation.json", generated)
        if arm != "ft_testing":
            (out / "raw.txt").write_text(generated["experiment_record"]["structured_output_attempts"][0]["raw_response"])
        print(json.dumps({"case": c.case_id, "arm": arm, **generation_observation(generated, arm)}), flush=True)
    except Exception as exc:
        write_json(out / "failure.json", generation_failure_payload(exc,
                   case_sha256=hashlib.sha256(case.model_dump_json().encode()).hexdigest(), arm=arm))
        print(json.dumps({"case": c.case_id, "arm": arm, "failure": str(exc)}), flush=True)


def summarize(root: Path, configs: list[Defects4JConfig]) -> dict:
    cells = []
    for c in configs:
        for arm in ARMS:
            cell = root / "cases" / c.case_id
            out = cell / "predictions" / arm
            gen = json.loads((out / "generation.json").read_text()) if (out / "generation.json").exists() else None
            failure = json.loads((out / "failure.json").read_text()) if (out / "failure.json").exists() else None
            evaluation = cell / "metrics" / arm / "evaluation.json"
            ev = json.loads(evaluation.read_text()) if evaluation.exists() else {}
            observation = generation_observation(gen, arm) if gen else {}
            row = {"case": c.case_id, "arm": arm, "planned": 1,
                   "attempted": int((out / "attempt.json").exists()), "generated": int(gen is not None),
                   "generation": observation, "generation_failure": failure,
                   "fixed_class_pass": ev.get("fixed_pass", False),
                   "genuine_bug_detection": ev.get("detected_bug", False),
                   "unstable": ev.get("unstable", False), "revisions": {}}
            for revision in ("fixed", "buggy"):
                runs = ev.get("outcomes", {}).get(revision, [])
                row["revisions"][revision] = [{"status": r["status"],
                    "compiled": bool(r.get("compile", {}).get("status") == "completed" and r["compile"]["returncode"] == 0),
                    **{key: r.get("console_summary", {}).get(key, 0) for key in
                       ("tests_started", "tests_successful", "tests_failed", "tests_aborted", "tests_skipped", "containers_failed")}}
                    for r in runs]
            row["compiled"] = bool(row["revisions"]["fixed"] and all(r["compiled"] for r in row["revisions"]["fixed"]))
            first = row["revisions"]["fixed"][:1]
            row["test_count_adherence_only"] = bool(first and 2 <= first[0]["tests_started"] <= 4)
            row["compile_invalid"] = any(r["status"] in {"invalid_source", "compile_failure"} for v in row["revisions"].values() for r in v)
            row["truncated"] = observation.get("truncated", False)
            row["schema_failure"] = bool(failure and failure.get("structured_output_attempts"))
            row["infrastructure_failure"] = any(r["status"] in {"infrastructure_error", "timeout"} for v in row["revisions"].values() for r in v)
            cells.append(row)
    metrics = ("attempted", "generated", "compiled", "fixed_class_pass", "genuine_bug_detection", "compile_invalid", "truncated", "schema_failure", "infrastructure_failure")
    def totals(rows):
        return {k: sum(int(r[k]) for r in rows) for k in metrics}
    return {"protocol": PROTOCOL, "denominator": 9, "per_arm_denominator": 3,
            "case_ids": [c.case_id for c in configs], "overall": totals(cells),
            "arms": {arm: totals([r for r in cells if r["arm"] == arm]) for arm in ARMS}, "cells": cells,
            "interpretation": "Exploratory systems comparison; overlap audit deferred by user. Same-project small sample; Lang-24 previously explored. HF PEFT/NF4 raw vs Ollama Q4 JSON is not causal FT ablation.",
            "test_counts": "Per-run counts (two repeats per revision); do not sum repeats as distinct tests. 2-4 is adherence only, not acceptance.",
            "coverage": "not_measured", "repairs": 0, "retries": 0,
            "sandbox": "none-reviewed-local-execution"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "generate", "evaluate", "report"])
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--run-id", required=True)
    p.add_argument("--arm", choices=ARMS)
    p.add_argument("--case")
    p.add_argument("--reviewed-local-execution", action="store_true")
    p.add_argument("--diagnostic", action="store_true")
    args = p.parse_args(argv)
    require_wsl()
    raw, configs = load_protocol(args.config)
    validate_evaluation_run_id(args.run_id)
    root = require_canonical_evaluation_path(Path("artifacts/evaluation/runs") / args.run_id).resolve()
    pins = identity(args.config, raw, configs)
    if args.action in {"prepare", "evaluate"} and not args.reviewed_local_execution:
        raise ValueError("Source review and --reviewed-local-execution required.")
    if args.action == "prepare":
        root.mkdir(parents=True, exist_ok=True)
        if (root / "freeze.json").exists():
            raise FileExistsError("Already frozen; preparation is never overwritten.")
        write_json(root / "job_plan.json", {"protocol": PROTOCOL, "max_generation_calls": 9,
                   "cells": [[c.case_id, arm] for c in configs for arm in ARMS], "attempts_per_cell": 1})
        frozen = {"identity": pins, "prepared": {}, "case_profiles": {}}
        for c in configs:
            case_root = root / "cases" / c.case_id
            case_root.mkdir(parents=True, exist_ok=True)
            if (case_root / "prepared.json").exists():
                prepared = json.loads((case_root / "prepared.json").read_text())
                verify_prepared(prepared, c, prepared_path=case_root / "prepared.json")
            else:
                prepared = prepare(c, case_root / "prepared.json")
            for revision in ("fixed", "buggy"):
                if (case_root / "health" / revision / "result.json").exists():
                    health = json.loads((case_root / "health" / revision / "result.json").read_text())
                    if health["status"] != "passed":
                        raise RuntimeError("Existing health failed.")
                    continue
                health = evaluate_revision(HEALTH % (c.focal_class, c.focal_class), prepared[revision],
                    output=case_root / "health" / revision, java_home=c.java_home,
                    junit_jar=c.junit_jar, junit_sha256=c.junit_sha256)
                if health["status"] != "passed":
                    raise RuntimeError("Model-free production/launcher health failed.")
            frozen["prepared"][c.case_id] = file_sha256(case_root / "prepared.json")
            frozen["case_profiles"][c.case_id] = {}
            for arm in ARMS:
                case = apply_profile(ExperimentCase.model_validate(prepared["case"]),
                                     envelope="ft" if arm == "ft_testing" else "rag")
                path = case_root / "prompts" / f"{arm}.json"
                write_json(path, case.model_dump(mode="json"))
                frozen["case_profiles"][c.case_id][arm] = file_sha256(path)
            print(json.dumps({"prepared": c.case_id, "health": "passed"}), flush=True)
        write_json(root / "freeze.json", frozen)
        return 0
    verify(root, pins, configs)
    if args.action == "report":
        report = summarize(root, configs)
        write_json(root / "reports/aggregate.json", report)
        print(json.dumps(report, indent=2))
        return 0
    if not args.arm:
        raise ValueError("--arm required.")
    selected = [c for c in configs if args.case in (None, c.case_id)]
    if not selected:
        raise ValueError("Case not preregistered.")
    if args.action == "generate":
        if not args.diagnostic:
            raise ValueError("Explicit --diagnostic required.")
        if args.arm == "ft_testing":
            # One unchanged local loader; reuse in memory for the three sequential cases.
            os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
            model_id = hf_identity(configs[0])
            loaded = load_eval_model(model_id["model"], {**model_id["inference"], "local_files_only": True, "trust_remote_code": False})
            try:
                for c in selected:
                    generate_cell(root, c, args.arm, loaded, model_id)
            finally:
                del loaded
                gc.collect()
                import torch
                torch.cuda.empty_cache()
        else:
            for c in selected:
                generate_cell(root, c, args.arm)
        return 0
    for c in selected:
        cell = root / "cases" / c.case_id
        out = cell / "predictions" / args.arm
        if (out / "failure.json").exists():
            continue
        gen = json.loads((out / "generation.json").read_text())
        if file_sha256(out / "generated.java") != gen["source_sha256"]:
            raise ValueError("Generated source changed; repairs forbidden.")
        write_json(out / "review.json", {"source_sha256": gen["source_sha256"], "reviewed_local_execution": True})
        ev = evaluate_pair(gen["source"], json.loads((cell / "prepared.json").read_text()),
            output=cell / "metrics" / args.arm, java_home=c.java_home, junit_jar=c.junit_jar,
            junit_sha256=c.junit_sha256, timeout=c.timeout_seconds, repeats=2)
        print(json.dumps({"case": c.case_id, "arm": args.arm, "fixed_pass": ev["fixed_pass"],
                          "detected_bug": ev["detected_bug"], "statuses": ev["statuses"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
