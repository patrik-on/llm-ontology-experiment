"""Five frozen EVAL cases x four systems; one dispatch per cell, no repair/retry."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

from llm_ontology.benchmarks import defects4j_direct_pilot as direct
from llm_ontology.benchmarks.defects4j import load_config, require_wsl
from llm_ontology.benchmarks.defects4j_execution import clean_env, evaluate_revision, file_sha256, run_process, write_json
from llm_ontology.benchmarks.defects4j_runner import (
    build_dependency_identity, generate_ft, generate_rag, generation_failure_payload, hf_identity, load_eval_model,
)
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentRunner
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.prompting.testing_bodies_v1 import assemble, sha
from llm_ontology.inference.structured_output import TestingBodiesAnswer, parse_testing_bodies
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.pipeline import VectorRetriever

ARMS = ("qwen_base", "ft_testing", "rag_single", "rag_multi")
CONFIG = Path("configs/benchmarks/methods2test_eval_five_v1.json")


def read(p):
    return json.loads(p.read_text())


def runtime():
    return load_config(Path("configs/benchmarks/defects4j_jupiter_v1.yaml")).model_copy(
        update={"prompt_profile": None, "max_new_tokens": 4096})


def ft_case(case):
    instruction = case.instruction + "\n" + case.requirements + "\n" + case.project_context + "\nJSON schema: " + json.dumps(TestingBodiesAnswer.model_json_schema(), sort_keys=True)
    return case.model_copy(update={"instruction": instruction})


def freeze(root):
    c = runtime()
    if (root / "freeze.json").exists():
        raise FileExistsError("Already frozen")
    selected = read(root / "selection.json")
    if len(selected["ids"]) != 5 or len(set(selected["ids"])) != 5:
        raise ValueError("Exactly five independent focal methods required")
    controls = {
        "pass": ('import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(4,2+2);} }', "passed"),
        "fail": ('import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(5,2+2);} }', "assertion_failure"),
        "empty": ('class Probe {}', "no_tests"),
    }
    revision = selected["cases"][0]["revision"]
    for name, (source, expected) in controls.items():
        result = evaluate_revision(source, revision, output=root / "controls" / name,
                                   java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256)
        if result["status"] != expected:
            raise ValueError("Jupiter control failed " + name)
    demo = root / "demo"
    demo.mkdir()
    (demo / "Labels.java").write_text(profile.DEMO_PRODUCTION)
    (demo / "GeneratedBodyTests.java").write_text(profile.demo_source())
    (demo / "block.txt").write_text(profile.DEMO_BLOCK)
    classes = demo / "production-classes"
    classes.mkdir()
    result = run_process([str(c.java_home / "bin/javac"), "-g", "-proc:none", "-d", str(classes), str(demo / "Labels.java")],
                         demo, clean_env(demo / "home", c.java_home), 30, demo / "compile.log")
    if result.get("returncode") != 0:
        raise ValueError("Demo production failed")
    result = evaluate_revision(profile.demo_source(), {"bin_classes": str(classes), "dependencies": []},
                               output=demo / "evaluation", java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256)
    if result["status"] != "passed" or result["console_summary"]["tests_started"] != 2:
        raise ValueError("Demo did not pass 2 tests")
    write_json(root / "hf_identity.json", hf_identity(c))
    provider = OllamaProvider(model_name=direct.MODELS["qwen_base"][0])
    if provider.resolve_model_digest() != c.generation_model_digest:
        raise ValueError("Qwen identity mismatch")
    write_json(root / "ollama_identity.json", provider.describe_model())
    manifest_dir = Path(load_rag_config(c.retrieval_config).vector_store.persist_path) / "manifests"
    write_json(root / "index_identity.json", {str(p): file_sha256(p) for p in sorted(manifest_dir.glob("*.json"))})
    write_json(root / "job_plan.json", read(CONFIG))
    write_json(root / "schema.json", TestingBodiesAnswer.model_json_schema())
    files = [root / n for n in ["selection.json", "leakage_audit.json", "job_plan.json", "hf_identity.json", "ollama_identity.json", "index_identity.json", "schema.json"]]
    for ident in selected["ids"]:
        cr = root / "cases" / ident
        case = ExperimentCase.model_validate(read(cr / "case.json"))
        for prompt in [profile.BodyPromptBuilder().build(task="testing", instruction=case.instruction, input_text=case.input_text,
                       requirements=case.requirements, project_context=case.project_context, contexts=(), approach="direct").text,
                       format_inference_prompt(ft_case(case).instruction, case.input_text)]:
            if prompt.count(profile.DEMO_BLOCK) != 1:
                raise ValueError("Missing substantive one-shot example")
            if read(cr / "raw-private.json")["raw"]["test_case"]["body"] in prompt:
                raise ValueError("Gold entered model prompt")
        (cr / "direct-preview.txt").write_text(profile.BodyPromptBuilder().build(task="testing", instruction=case.instruction,
            input_text=case.input_text, requirements=case.requirements, project_context=case.project_context, contexts=(), approach="direct").text)
        (cr / "ft-preview.txt").write_text(format_inference_prompt(ft_case(case).instruction, case.input_text))
        files.extend(cr / n for n in ["case.json", "scaffold.java", "prepared.json", "raw-private.json", "reference-private.java", "direct-preview.txt", "ft-preview.txt"])
        files.extend(Path(read(cr / "prepared.json")["revision"]["bin_classes"]).rglob("*.class"))
    files.extend(Path(p) for p in ["configs/datasets/manifests/methods2test_unused_eval_v1.json", "data/validation/methods2test_unused_eval_v1/selection.jsonl", "configs/evaluation/methods2test_assertions_v1.json", "configs/evaluation/jacoco_v1.json"])
    files.extend(root.glob("cases/*/rich-original-private.json"))
    files.extend(root.glob("cases/*/*.java"))
    sources = build_dependency_identity(c)
    for name in sources:
        source = Path(name)
        dest = root / "source_snapshot" / source.relative_to(Path.cwd())
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    write_json(root / "freeze.json", {"files": {str(p): file_sha256(p) for p in files}, "sources": sources,
               "config": file_sha256(CONFIG), "created_before_model_calls": True,
               "java": {str(p): file_sha256(p) for p in [c.java_home / "bin/java", c.java_home / "bin/javac", c.junit_jar]}})
    print("FROZEN", selected["ids"], flush=True)


def verify(root):
    f = read(root / "freeze.json")
    for key in ["files", "sources", "java"]:
        for p, digest in f[key].items():
            if file_sha256(Path(p)) != digest:
                raise ValueError("Frozen dependency changed: " + p)
    if file_sha256(CONFIG) != f["config"]:
        raise ValueError("Protocol changed")
    for p, digest in read(root / "index_identity.json").items():
        if file_sha256(Path(p)) != digest:
            raise ValueError("Index changed")


class Ledger:
    def __init__(self, root, ident, arm):
        self.root, self.ident, self.arm = root, ident, arm
        if ident not in read(root / "selection.json")["ids"] or arm not in ARMS:
            raise ValueError("Unplanned cell")
        self.out = root / "cases" / ident / "predictions" / arm

    def charge(self, payload):
        with (self.out / "dispatch.json").open("x") as handle:
            json.dump({"charged_to_budget": True, "id": self.ident, "arm": self.arm, "request": payload, "maximum": 20}, handle, indent=2)
        self.dispatch_time = perf_counter()
        if len(list(self.root.glob("cases/*/predictions/*/dispatch.json"))) > 20:
            raise RuntimeError("Budget exceeded")

    def __call__(self, request, **kwargs):
        base = "http://localhost:11434/api/"
        if request.full_url in [base + p for p in ["tags", "show", "version"]]:
            return urlopen(request, **kwargs)
        if request.full_url != base + "generate":
            raise ValueError("Unapproved model endpoint")
        payload = json.loads(request.data)
        if payload["options"] != {"temperature": 0.0, "top_p": .9, "num_predict": 4096, "num_ctx": 32768, "seed": 42} or payload.get("format") != TestingBodiesAnswer.model_json_schema():
            raise ValueError("Sampling/schema mismatch")
        if payload["model"] != direct.MODELS["qwen_base"][0]:
            raise ValueError("Wrong model")
        payload["keep_alive"] = 0
        self.charge(payload)
        request = Request(request.full_url, data=json.dumps(payload).encode(), headers=dict(request.headers), method="POST")
        try:
            with urlopen(request, **kwargs) as response:
                raw = response.read()
            (self.out / "server_response.json").write_bytes(raw)
            (self.out / "raw.txt").write_text(json.loads(raw).get("response", ""))
            return BytesIO(raw)
        except Exception as exc:
            if hasattr(exc, "read"):
                (self.out / "http_error.txt").write_bytes(exc.read())
            raise


def direct_usable(root):
    first = read(root / "selection.json")["ids"][0]
    p = root / "cases" / first / "predictions/qwen_base/compatibility.json"
    return p.exists() and read(p)["usable"]


def generate(root, arm, first_only=False):
    verify(root)
    if (arm != "qwen_base" or not first_only) and not direct_usable(root):
        raise ValueError("Direct-first compile/positive execution compatibility gate not met")
    c = runtime()
    ids = read(root / "selection.json")["ids"]
    if first_only:
        ids = ids[:1]
    identity = read(root / "hf_identity.json")
    loaded = None
    if arm == "ft_testing":
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        started = perf_counter()
        loaded = load_eval_model(identity["model"], {**identity["inference"], "local_files_only": True, "trust_remote_code": False})
        write_json(root / "ft_load.json", {"seconds": perf_counter() - started, "loaded_once_for_up_to_five": True})
    for ident in ids:
        out = root / "cases" / ident / "predictions" / arm
        if (out / "dispatch.json").exists():
            if not (out / "completion.json").exists():
                raise ValueError("Interrupted charged cell; no automatic retry")
            continue
        out.mkdir(parents=True, exist_ok=False)
        case = ExperimentCase.model_validate(read(root / "cases" / ident / "case.json"))
        ledger = Ledger(root, ident, arm)
        started = perf_counter()
        raw = ""
        try:
            if arm == "ft_testing":
                generated = generate_ft(c, ft_case(case), out, loaded_model=loaded, model_identity=identity,
                    before_generation=lambda prompt: ledger.charge({"prompt": prompt, "max_new_tokens": 4096, "do_sample": False, "seed": 42}))
                generated["dispatch_to_return_seconds"] = perf_counter() - ledger.dispatch_time
                raw = (out / "raw.txt").read_text()
            elif arm == "qwen_base":
                tokens = direct.counter()
                provider = OllamaProvider(model_name=direct.MODELS[arm][0], temperature=0, top_p=.9, max_tokens=4096,
                    context_window_tokens=32768, seed=42, timeout_seconds=1800, opener=ledger)
                runner = RagExperimentRunner(retriever=VectorRetriever(direct.ForbiddenStore()), llm_provider=provider,
                    token_counter=tokens, total_context_tokens=32768, reserved_output_tokens=4096, runtime_context_tokens=32768,
                    fail_on_prompt_budget_exceeded=True, structured_retries=0, prompt_builder=profile.BodyPromptBuilder(), structured_answer_model=TestingBodiesAnswer)
                exp = direct.experiment(out, arm, tokens).model_copy(update={"baseline_id": "methods2test_eval_five_v1", "dataset_version": "methods2test-unused-eval-v1"})
                record = runner.run_case(exp, case)
                generated = {"experiment_record": record.model_dump(mode="json")}
                raw = record.structured_output_attempts[0]["raw_response"]
            else:
                generated = generate_rag(c, case, out, arm, read(root / "leakage_audit.json"), body_profile=True, opener=ledger)
                raw = generated["experiment_record"]["structured_output_attempts"][0]["raw_response"]
            (out / "raw.txt").write_text(raw)
            write_json(out / "received.json", generated)
            answer = parse_testing_bodies(raw)
            write_json(out / "bodies.json", answer.model_dump())
            source = assemble((root / "cases" / ident / "scaffold.java").read_text(), answer)
            (out / "generated.java").write_text(source)
            write_json(out / "generation.json", {**generated, "source_sha256": sha(source), "assembled": True})
            write_json(out / "completion.json", {"assembled": True, "generation_pipeline_seconds": perf_counter() - started})
            print("GENERATED", arm, ident, flush=True)
        except Exception as exc:
            write_json(out / "failure.json", generation_failure_payload(exc, case_sha256=file_sha256(root / "cases" / ident / "case.json"), arm=arm))
            write_json(out / "completion.json", {"assembled": False, "generation_pipeline_seconds": perf_counter() - started})
            print("FAILURE", arm, ident, str(exc), flush=True)
            server = read(out / "server_response.json") if (out / "server_response.json").exists() else {}
            if not raw and not server.get("response"):
                write_json(root / (arm + "-stop.json"), {"id": ident, "reason": "empty response or transport/protocol infrastructure anomaly; no remaining calls"})
                break


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["freeze", "generate", "compatibility"])
    p.add_argument("--reviewed-source-sha256")
    p.add_argument("--run-id", required=True)
    p.add_argument("--arm", choices=ARMS)
    p.add_argument("--first-only", action="store_true")
    args = p.parse_args()
    require_wsl()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
    validate_evaluation_run_id(args.run_id)
    root = (Path("artifacts/evaluation/runs") / args.run_id).resolve()
    if args.action == "freeze":
        freeze(root)
    elif args.action == "compatibility":
        ident = read(root / "selection.json")["ids"][0]
        out = root / "cases" / ident / "predictions/qwen_base"
        if file_sha256(out / "generated.java") != args.reviewed_source_sha256:
            raise ValueError("Explicit matching source review required")
        c = runtime()
        ev = evaluate_revision((out / "generated.java").read_text(), read(root / "cases" / ident / "prepared.json")["revision"],
            output=out / "compatibility", java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256)
        usable = ev.get("compile", {}).get("returncode") == 0 and ev.get("console_summary", {}).get("tests_started", 0) > 0
        write_json(out / "compatibility.json", {"usable": usable, "status": ev["status"], "reviewed_source_sha256": args.reviewed_source_sha256})
    else:
        if not args.arm:
            raise ValueError("Explicit arm required")
        if (root / (args.arm + "-stop.json")).exists():
            raise ValueError("Arm fail-stop recorded")
        generate(root, args.arm, args.first_only)


if __name__ == "__main__":
    main()
