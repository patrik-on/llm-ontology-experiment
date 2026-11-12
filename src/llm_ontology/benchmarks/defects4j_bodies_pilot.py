"""One frozen real case, direct-first gate, <=4 calls, no repairs or retries."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
from urllib.request import Request, urlopen

from llm_ontology.benchmarks import defects4j_direct_pilot as direct
from llm_ontology.benchmarks.defects4j import require_wsl, verify_prepared
from llm_ontology.benchmarks.defects4j_execution import evaluate_pair, evaluate_revision, file_sha256, write_json
from llm_ontology.benchmarks.defects4j_pilot import DEFAULT_CONFIG, load_protocol
from llm_ontology.benchmarks.defects4j_runner import (
    build_dependency_identity, generate_ft, generate_rag, generation_failure_payload, hf_identity,
)
from llm_ontology.evaluation.run_layout import require_canonical_evaluation_path, validate_evaluation_run_id
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentRunner
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.inference.prompting.testing_bodies_v1 import (
    PROFILE, CONTRACT, assemble, scaffold, sha,
)
from llm_ontology.inference.structured_output import TestingBodiesAnswer, parse_testing_bodies
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.pipeline import VectorRetriever

PROTOCOL = "defects4j_qwen_shared_bodies_v1"
ARMS = ("qwen_base", "ft_testing", "rag_single", "rag_multi")
CONFIG = Path("configs/benchmarks/defects4j_qwen_shared_bodies_v1.json")
ONE_SHOT_CONFIG = Path("configs/benchmarks/defects4j_qwen_bodies_one_shot_v2.json")


def profile_module(name):
    from llm_ontology.inference.prompting import testing_bodies_v1, testing_bodies_one_shot_v2
    profiles = {m.PROFILE: m for m in (testing_bodies_v1, testing_bodies_one_shot_v2)}
    return profiles[name]


def read(path):
    return json.loads(path.read_text())


def inputs():
    _, configs = load_protocol(DEFAULT_CONFIG)
    c = next(c for c in configs if c.case_id == "Lang-26")
    path = direct.OLD / "cases/Lang-26/prepared.json"
    if file_sha256(path) != read(direct.OLD / "freeze.json")["prepared"][c.case_id]:
        raise ValueError("Original prepared file changed.")
    prepared = read(path)
    verify_prepared(prepared, c, prepared_path=path)
    for revision in ("fixed", "buggy"):
        health = direct.OLD / "cases/Lang-26/health" / revision / "result.json"
        if read(health)["status"] != "passed":
            raise ValueError("Existing prepared health failed.")
    return c, path, prepared


def pins(c, path, config=CONFIG):
    return {"sources": build_dependency_identity(c), "config": file_sha256(config),
            "prepared": file_sha256(path), "profile": read(config)["prompt_profile"],
            "policy": sha(CONTRACT), "java": file_sha256(c.java_home / "bin/java"),
            "javac": file_sha256(c.java_home / "bin/javac"), "junit": file_sha256(c.junit_jar)}


def usable(root):
    path = root / "predictions/qwen_base/metrics/evaluation.json"
    if not path.exists():
        return False
    runs = read(path)["outcomes"]["fixed"]
    return len(runs) == 2 and all(
        r.get("compile", {}).get("returncode") == 0
        and r.get("console_summary", {}).get("tests_started", 0) > 0
        and r["status"] in {"passed", "assertion_failure", "execution_error"}
        for r in runs)


class Ledger:
    """Exclusive per-arm dispatch; failed requests consume the call. No alternate client."""
    def __init__(self, root, arm):
        self.root, self.arm = root, arm
        plan = read(root / "job_plan.json") if (root / "job_plan.json").exists() else read(CONFIG)
        self.maximum = plan["max_actual_generation_calls"]
        if arm not in plan["arms"]:
            raise ValueError("Unknown arm.")

    def charge(self, request):
        if self.arm != "qwen_base" and not usable(self.root):
            raise ValueError("Direct-first functional execution gate not met; STOP.")
        if self.maximum == 3:
            from llm_ontology.benchmarks.defects4j_bodies_one_shot import verify_request
            verify_request(self.root, self.arm, request)
        # The fixed finite arm set plus exclusive dispatch files imposes the atomic cap.
        path = self.root / "predictions" / self.arm / "dispatch.json"
        with path.open("x") as handle:
            json.dump({"charged_to_budget": True, "maximum": self.maximum, "arm": self.arm,
                       "request": request}, handle, indent=2)

    def __call__(self, request, **kwargs):
        base = "http://localhost:11434/api/"
        if request.full_url in [base + x for x in ("tags", "show", "version")]:
            return urlopen(request, **kwargs)
        if request.full_url != base + "generate":
            raise ValueError("Only existing WSL Ollama generate transport permitted.")
        payload = json.loads(request.data)
        expected_options = {"temperature": 0.0, "top_p": .9, "num_predict": 4096, "num_ctx": 32768, "seed": 42}
        if (payload["model"] != direct.MODELS["qwen_base"][0]
                or payload["options"] != expected_options
                or payload.get("format") != TestingBodiesAnswer.model_json_schema()):
            raise ValueError("Frozen model/schema/decoding changed.")
        payload["keep_alive"] = 0
        self.charge(payload)
        request = Request(request.full_url, data=json.dumps(payload).encode(),
                          headers=dict(request.headers), method="POST")
        out = self.root / "predictions" / self.arm
        try:
            with urlopen(request, **kwargs) as response:
                raw = response.read()
            (out / "server_response.json").write_bytes(raw)
            (out / "raw.txt").write_text(json.loads(raw).get("response", ""))
            return BytesIO(raw)
        except Exception as exc:
            if hasattr(exc, "read"):
                (out / "http_error.txt").write_bytes(exc.read())
            raise


def freeze(root, c, path, prepared, config=CONFIG):
    root.mkdir(parents=True, exist_ok=False)
    original = ExperimentCase.model_validate(prepared["case"])
    plan = read(config)
    profile = profile_module(plan["prompt_profile"])
    case = profile.apply_profile(original)
    case.metadata["protocol"] = plan["protocol"]
    write_json(root / "case.json", case.model_dump(mode="json"))
    (root / "scaffold.java").write_text(scaffold(original))
    write_json(root / "schema.json", TestingBodiesAnswer.model_json_schema())
    write_json(root / "job_plan.json", plan)
    # Evaluator-only nonvacuous launcher/scaffold controls, never part of case/prompt.
    controls = TestingBodiesAnswer(testCase1="assertEquals(4, 2 + 2);", testCase2='assertThrows(IllegalArgumentException.class, () -> { throw new IllegalArgumentException(); });')
    good = assemble(scaffold(original), controls)
    bad = assemble(scaffold(original), controls.model_copy(update={"testCase1": "assertEquals(5, 2 + 2);"}))
    for name, source, status in (("pass", good, "passed"), ("assertion", bad, "assertion_failure")):
        result = evaluate_revision(source, prepared["fixed"], output=root / "controls" / name,
            java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256,
            timeout=c.timeout_seconds)
        if result["status"] != status or result.get("console_summary", {}).get("tests_started") != 2:
            raise ValueError("Model-free scaffold control failed.")
    name, digest, _ = direct.MODELS["qwen_base"]
    provider = OllamaProvider(model_name=name)
    if provider.resolve_model_digest() != digest:
        raise ValueError("Installed Qwen digest mismatch.")
    write_json(root / "ollama_model.json", provider.describe_model())
    write_json(root / "hf_identity.json", hf_identity(c))
    manifests = Path(load_rag_config(c.retrieval_config).vector_store.persist_path) / "manifests"
    if len(list(manifests.glob("*.json"))) < 3:
        raise ValueError("Existing index manifests unavailable.")
    write_json(root / "index_identity.json", {str(p): file_sha256(p) for p in sorted(manifests.glob("*.json"))})
    for source in build_dependency_identity(c):
        source = Path(source)
        target = root / "source_snapshot" / source.relative_to(Path.cwd())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    extra = []
    if plan["prompt_profile"] != PROFILE:
        from llm_ontology.benchmarks.defects4j_bodies_one_shot import preflight
        extra = preflight(root, c, case)
    write_json(root / "freeze.json", {"pins": pins(c, path, config), "files": {
        name: file_sha256(root / name) for name in ("case.json", "scaffold.java", "schema.json", "job_plan.json", "ollama_model.json", "hf_identity.json", "index_identity.json", *extra)}})


def verify(root, c, path, config=CONFIG):
    frozen = read(root / "freeze.json")
    if frozen["pins"] != pins(c, path, config):
        raise ValueError("Frozen source/config/prepared identity changed; no resume generation.")
    for name, digest in frozen["files"].items():
        if file_sha256(root / name) != digest:
            raise ValueError("Frozen artifact changed: " + name)
    for name, digest in read(root / "index_identity.json").items():
        if file_sha256(Path(name)) != digest:
            raise ValueError("Index manifest changed.")


def generate(root, c, arm):
    if arm != "qwen_base" and not usable(root):
        raise ValueError("Direct-first gate failed; no additional calls authorized.")
    out = root / "predictions" / arm
    out.mkdir(parents=True, exist_ok=False)
    case = ExperimentCase.model_validate(read(root / "case.json"))
    c = c.model_copy(update={"prompt_profile": None, "max_new_tokens": 4096})
    ledger = Ledger(root, arm)
    plan = read(root / "job_plan.json")
    profile = profile_module(plan["prompt_profile"])
    try:
        if arm == "ft_testing":
            # Same functional task/scaffold/API, historical raw instruction envelope only.
            instruction = case.instruction + "\n" + case.requirements + "\n" + case.project_context + "\nJSON schema: " + json.dumps(TestingBodiesAnswer.model_json_schema(), sort_keys=True)
            ftcase = case.model_copy(update={"instruction": instruction})
            generated = generate_ft(c, ftcase, out, model_identity=read(root / "hf_identity.json"),
                before_generation=lambda prompt: ledger.charge({"prompt": prompt, "max_new_tokens": 4096, "do_sample": False, "seed": 42}))
            raw = (out / "raw.txt").read_text()
        elif arm == "qwen_base":
            tokens = direct.counter()
            name, digest, _ = direct.MODELS[arm]
            provider = OllamaProvider(model_name=name, temperature=0, top_p=.9, max_tokens=4096,
                context_window_tokens=32768, seed=42, timeout_seconds=1800, opener=ledger)
            if provider.resolve_model_digest() != digest:
                raise ValueError("Installed Qwen changed.")
            runner = RagExperimentRunner(retriever=VectorRetriever(direct.ForbiddenStore()),
                llm_provider=provider, token_counter=tokens, total_context_tokens=32768,
                reserved_output_tokens=4096, runtime_context_tokens=32768,
                fail_on_prompt_budget_exceeded=True, structured_retries=0,
                prompt_builder=profile.BodyPromptBuilder(), structured_answer_model=TestingBodiesAnswer)
            exp = direct.experiment(out, arm, tokens).model_copy(update={"baseline_id": plan["protocol"]})
            record = runner.run_case(exp, case)
            generated = {"experiment_record": record.model_dump(mode="json")}
            raw = record.structured_output_attempts[0]["raw_response"]
        else:
            generated = generate_rag(c, case, out, arm, {"audit_status": "deferred_by_user"}, body_profile=True, opener=ledger)
            raw = generated["experiment_record"]["structured_output_attempts"][0]["raw_response"]
        (out / "raw.txt").write_text(raw)
        # Persist before parse/structural failure. No repair/whole-class extraction.
        write_json(out / "received.json", generated)
        answer = parse_testing_bodies(raw)
        write_json(out / "bodies.json", answer.model_dump())
        source = assemble((root / "scaffold.java").read_text(), answer)
        (out / "generated.java").write_text(source)
        write_json(out / "generation.json", {**generated, "source": source,
            "source_sha256": sha(source), "body_format_parsed": True, "assembled": True,
            "policy_sha256": sha(CONTRACT), "scaffold_sha256": file_sha256(root / "scaffold.java")})
        print(json.dumps({"arm": arm, "assembled": True, "source_sha256": sha(source)}), flush=True)
    except Exception as exc:
        write_json(out / "failure.json", generation_failure_payload(exc, case_sha256=file_sha256(root / "case.json"), arm=arm))
        print(json.dumps({"arm": arm, "failure": str(exc)}), flush=True)


def report(root):
    rows = []
    plan = read(root / "job_plan.json")
    for arm in plan["arms"]:
        out = root / "predictions" / arm
        evpath = out / "metrics/evaluation.json"
        ev = read(evpath) if evpath.exists() else {}
        failure = read(out / "failure.json") if (out / "failure.json").exists() else None
        server = read(out / "server_response.json") if (out / "server_response.json").exists() else {}
        ft = read(out / "generation_metadata.json") if (out / "generation_metadata.json").exists() else {}
        revisions = {rev: [{"status": r["status"], "compiled": r.get("compile", {}).get("returncode") == 0,
            **r.get("console_summary", {})} for r in ev.get("outcomes", {}).get(rev, [])] for rev in ("fixed", "buggy")}
        rows.append({"arm": arm, "actual_calls": int((out / "dispatch.json").exists()),
            "body_format_parsed": (out / "bodies.json").exists(), "assembled": (out / "generation.json").exists(),
            "fixed_pass": ev.get("fixed_pass", False), "genuine_bug_detection": ev.get("detected_bug", False),
            "revisions": revisions, "failure": failure, "finish": server.get("done_reason", ft.get("finish_reason")),
            "output_tokens": server.get("eval_count", ft.get("output_tokens")),
            "input_tokens": server.get("prompt_eval_count", ft.get("input_tokens")),
            "truncated": server.get("done_reason") == "length" or ft.get("output_truncated", False),
            "infrastructure_failure": any(r["status"] in {"infrastructure_error", "timeout", "container_failure"} for rs in revisions.values() for r in rs)})
    result = {"protocol": plan["protocol"], "case": "Lang-26", "max_actual_calls": plan["max_actual_generation_calls"],
        "actual_calls": sum(r["actual_calls"] for r in rows), "direct_usable": usable(root), "arms": rows,
        "retries": 0, "repairs": 0, "coverage": "not_measured", "scientific_score": False,
        "limitations": ["One diagnostic same-project case; no improvement or isolated FT ablation claim.",
            "HF PEFT NF4 raw instruction vs Ollama Q4 schema-constrained generate; no retraining.",
            "Known retrieval method/query/regex/reranking defects remain unchanged; overlap investigation deferred.",
            "Reviewed local scrubbed execution is not a security sandbox."]}
    write_json(root / "reports/aggregate.json", result)
    print(json.dumps(result, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "generate", "evaluate", "report"))
    p.add_argument("--run-id", required=True)
    p.add_argument("--config", type=Path, default=CONFIG, choices=(CONFIG, ONE_SHOT_CONFIG))
    p.add_argument("--arm", choices=ARMS)
    p.add_argument("--diagnostic", action="store_true")
    p.add_argument("--reviewed-source-sha256")
    args = p.parse_args(argv)
    require_wsl()
    validate_evaluation_run_id(args.run_id)
    root = require_canonical_evaluation_path(Path("artifacts/evaluation/runs") / args.run_id).resolve()
    c, path, prepared = inputs()
    if args.action == "freeze":
        freeze(root, c, path, prepared, args.config)
        return
    verify(root, c, path, args.config)
    if args.arm and args.arm not in read(root / "job_plan.json")["arms"]:
        raise ValueError("Arm not authorized by frozen protocol.")
    if args.action == "report":
        report(root)
    elif args.action == "generate":
        if not args.diagnostic or not args.arm:
            raise ValueError("Explicit diagnostic and arm required.")
        generate(root, c, args.arm)
    else:
        if not args.arm:
            raise ValueError("Arm required.")
        out = root / "predictions" / args.arm
        generated = read(out / "generation.json")
        if (file_sha256(out / "generated.java") != generated["source_sha256"]
                or args.reviewed_source_sha256 != generated["source_sha256"]):
            raise ValueError("Source changed or matching local review missing; no repairs.")
        write_json(out / "review.json", {"reviewed_local_execution": True, "source_sha256": args.reviewed_source_sha256})
        result = evaluate_pair(generated["source"], prepared, output=out / "metrics", java_home=c.java_home,
            junit_jar=c.junit_jar, junit_sha256=c.junit_sha256, timeout=c.timeout_seconds, repeats=2)
        print(json.dumps({"arm": args.arm, "fixed_pass": result["fixed_pass"],
                          "detected_bug": result["detected_bug"], "statuses": result["statuses"]}), flush=True)


if __name__ == "__main__":
    main()
