"""Opt-in six-call pure-model control; compose existing runner/evaluator, no index."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from llm_ontology.approaches import ApproachPromptBuilder
from llm_ontology.benchmarks.defects4j import require_wsl, verify_prepared
from llm_ontology.benchmarks.defects4j_execution import evaluate_pair, file_sha256, write_json
from llm_ontology.benchmarks.defects4j_pilot import DEFAULT_CONFIG, identity, load_protocol
from llm_ontology.benchmarks.defects4j_runner import generation_failure_payload
from llm_ontology.evaluation.run_layout import require_canonical_evaluation_path, validate_evaluation_run_id
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentConfig, RagExperimentRunner
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.inference.structured_output import TestingAnswer
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter

PROTOCOL = "defects4j_direct_pure_full_class_v2"
OLD = Path("artifacts/evaluation/runs/real-d4j-fullclass-v2-20261112")
MODELS = {
    "qwen_base": ("qwen2.5-coder:7b", "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364", None),
    "gptoss20b": ("gpt-oss:20b", "17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7", "low"),
}
TOKENIZER = Path("/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct")


def read_json(path):
    return json.loads(path.read_text())


class ForbiddenStore:
    def __getattr__(self, name):
        raise AssertionError(f"Direct pilot forbids vector-store access: {name}")


class RequestLedger:
    """One exclusive actual dispatch per cell, including failed HTTP requests."""
    def __init__(self, root, output):
        self.root, self.output = root, output

    def __call__(self, request, **kwargs):
        if request.full_url.endswith("/api/generate"):
            payload = json.loads(request.data)
            payload["keep_alive"] = 0  # Sequential GPU ownership, no lingering model.
            request = Request(request.full_url, data=json.dumps(payload).encode(),
                              headers=dict(request.headers), method=request.get_method())
            ledger = self.output / "dispatch.json"
            with ledger.open("x") as handle:
                json.dump({"charged_to_budget": True, "request": payload}, handle, indent=2)
            if len(list(self.root.glob("cases/*/predictions/*/dispatch.json"))) > 6:
                raise RuntimeError("Six-call cap exceeded.")
            try:
                response = urlopen(request, **kwargs)
                raw = response.read()
                (self.output / "server_response.json").write_bytes(raw)
                response.close()
            except Exception as exc:
                if hasattr(exc, "read"):
                    (self.output / "http_error.txt").write_bytes(exc.read())
                raise
            # Preserve the existing provider's ordinary context-managed response contract.
            from io import BytesIO
            return BytesIO(raw)
        return urlopen(request, **kwargs)


def counter():
    return HuggingFaceTokenCounter(model_identifier=str(TOKENIZER),
                                  model_revision=file_sha256(TOKENIZER / "tokenizer.json"))


def experiment(output, arm, tokens):
    return RagExperimentConfig(
        enabled=True, baseline_id=PROTOCOL, requested_task="testing", retrieval_mode="no_rag",
        dataset_version="defects4j-3.0.1-three-case-direct-control", embedding_model="none",
        embedding_revision="not_used", llm_model=MODELS[arm][0], generation_max_tokens=4096,
        tokenizer_model=tokens.model_identifier, tokenizer_revision=tokens.model_revision,
        total_context_tokens=32768, reserved_output_tokens=4096, safety_margin_tokens=256,
        runtime_context_tokens=32768, fail_on_prompt_budget_exceeded=True,
        results_path=output / "experiment.jsonl", prompt_artifacts_dir=output / "prompts")


def current_pins(raw, configs):
    return {"identity": identity(DEFAULT_CONFIG, raw, configs),
            "models": MODELS, "tokenizer_sha256": file_sha256(TOKENIZER / "tokenizer.json")}


def verify(root, raw, configs):
    frozen = read_json(root / "freeze.json")
    if frozen["pins"] != json.loads(json.dumps(current_pins(raw, configs))):
        raise ValueError("New-run code/config identity changed; resume prohibited.")
    for c in configs:
        path = OLD / "cases" / c.case_id / "prepared.json"
        if file_sha256(path) != frozen["prepared"][c.case_id]:
            raise ValueError("Prepared file changed.")
        verify_prepared(read_json(path), c, prepared_path=path)
        if file_sha256(root / "cases" / c.case_id / "case.json") != frozen["cases"][c.case_id]:
            raise ValueError("Frozen case changed.")
    return frozen


def freeze(root, raw, configs):
    if (root / "freeze.json").exists():
        raise FileExistsError("Already frozen.")
    root.mkdir(parents=True, exist_ok=True)
    frozen = {"pins": current_pins(raw, configs), "prepared": {}, "cases": {}, "prompts": {}}
    old = read_json(OLD / "freeze.json")
    for c in configs:
        path = OLD / "cases" / c.case_id / "prepared.json"
        if file_sha256(path) != old["prepared"][c.case_id]:
            raise ValueError("Original prepared hash mismatch.")
        verify_prepared(read_json(path), c, prepared_path=path)
        original = OLD / "cases" / c.case_id / "prompts/rag_single.json"
        if file_sha256(original) != old["case_profiles"][c.case_id]["rag_single"]:
            raise ValueError("Original profile hash mismatch.")
        case = ExperimentCase.model_validate_json(original.read_text())
        out = root / "cases" / c.case_id
        write_json(out / "case.json", case.model_dump(mode="json"))
        prompt = ApproachPromptBuilder().build(task="testing", instruction=case.instruction,
            input_text=case.input_text, requirements=case.requirements,
            project_context=case.project_context, approach="direct")
        (out / "direct_prompt.txt").write_text(prompt.text)
        frozen["prepared"][c.case_id] = file_sha256(path)
        frozen["cases"][c.case_id] = file_sha256(out / "case.json")
        frozen["prompts"][c.case_id] = {"full": prompt.full_prompt_sha256,
                                      "normalized": prompt.normalized_prompt_sha256}
    for arm, (name, digest, think) in MODELS.items():
        provider = OllamaProvider(model_name=name)
        if provider.resolve_model_digest() != digest:
            raise ValueError("Installed model identity mismatch.")
        show = provider.describe_model()
        if think and "thinking" not in show.get("capabilities", []):
            raise ValueError("Requested reasoning mode unavailable.")
        write_json(root / "models" / f"{arm}.json", show)
    write_json(root / "server_version.json", provider._request_json("/api/version", None, method="GET"))
    write_json(root / "job_plan.json", {"protocol": PROTOCOL, "max_actual_generation_calls": 6,
        "attempts_per_cell": 1, "retries": 0, "repairs": 0,
        "cells": [[c.case_id, arm] for arm in MODELS for c in configs],
        "reasoning": "GPT-OSS low, shares 4096 total output budget; final/reasoning token split not returned by Ollama",
        "local_execution": "review_required_no_sandbox", "overlap_audit": "deferred_by_user"})
    for source in frozen["pins"]["identity"]["sources"]:
        path = Path(source)
        try:
            relative = path.relative_to(Path.cwd())
        except ValueError:
            continue
        target = root / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    write_json(root / "freeze.json", frozen)


def generate(root, configs, arm):
    tokens = counter()
    for c in configs:
        out = root / "cases" / c.case_id / "predictions" / arm
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / "attempt.json", {"attempt": 1, "case": c.case_id, "arm": arm, "cap": 6})
        case = ExperimentCase.model_validate_json((out.parents[1] / "case.json").read_text())
        name, digest, think = MODELS[arm]
        provider = OllamaProvider(model_name=name, max_tokens=4096, context_window_tokens=32768,
            temperature=0, top_p=.9, seed=42, timeout_seconds=1800, think=think,
            opener=RequestLedger(root, out))
        if provider.resolve_model_digest() != digest:
            raise ValueError("Model digest changed.")
        runner = RagExperimentRunner(retriever=VectorRetriever(ForbiddenStore()), llm_provider=provider,
            token_counter=tokens, total_context_tokens=32768, reserved_output_tokens=4096,
            safety_margin_tokens=256, runtime_context_tokens=32768,
            fail_on_prompt_budget_exceeded=True, structured_retries=0)
        write_json(out / "schema.json", TestingAnswer.model_json_schema())
        try:
            record = runner.run_case(experiment(out, arm, tokens), case)
            frozen = read_json(root / "freeze.json")["prompts"][c.case_id]
            if record.full_prompt_sha256 != frozen["full"] or record.normalized_prompt_sha256 != frozen["normalized"]:
                raise ValueError("Actual prompt changed.")
            source = TestingAnswer.model_validate_json(record.response).generated_tests
            (out / "generated.java").write_text(source)
            write_json(out / "generation.json", {"source": source, "source_sha256": file_sha256(out / "generated.java"),
                "experiment_record": record.model_dump(mode="json")})
            print(json.dumps({"case": c.case_id, "arm": arm, "schema_valid": True}), flush=True)
        except Exception as exc:
            write_json(out / "failure.json", generation_failure_payload(exc,
                case_sha256=hashlib.sha256(case.model_dump_json().encode()).hexdigest(), arm=arm))
            print(json.dumps({"case": c.case_id, "arm": arm, "failure": str(exc)}), flush=True)


def evaluate(root, configs, arm):
    for c in configs:
        out = root / "cases" / c.case_id / "predictions" / arm
        if (out / "failure.json").exists():
            continue
        generated = read_json(out / "generation.json")
        if file_sha256(out / "generated.java") != generated["source_sha256"]:
            raise ValueError("Source changed; repairs forbidden.")
        write_json(out / "review.json", {"reviewed_local_execution": True, "source_sha256": generated["source_sha256"]})
        result = evaluate_pair(generated["source"], read_json(OLD / "cases" / c.case_id / "prepared.json"),
            output=out.parents[1] / "metrics" / arm, java_home=c.java_home,
            junit_jar=c.junit_jar, junit_sha256=c.junit_sha256, timeout=c.timeout_seconds, repeats=2)
        print(json.dumps({"case": c.case_id, "arm": arm, "fixed_pass": result["fixed_pass"],
                          "detected_bug": result["detected_bug"], "statuses": result["statuses"]}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "generate", "evaluate"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", choices=MODELS)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--reviewed-local-execution", action="store_true")
    args = parser.parse_args(argv)
    require_wsl()
    validate_evaluation_run_id(args.run_id)
    root = require_canonical_evaluation_path(Path("artifacts/evaluation/runs") / args.run_id).resolve()
    raw, configs = load_protocol(DEFAULT_CONFIG)
    if args.action == "freeze":
        freeze(root, raw, configs)
        return
    verify(root, raw, configs)
    if not args.arm:
        raise ValueError("--arm required.")
    if args.action == "generate":
        if not args.diagnostic:
            raise ValueError("--diagnostic required.")
        generate(root, configs, args.arm)
    else:
        if not args.reviewed_local_execution:
            raise ValueError("Review source first; --reviewed-local-execution required.")
        evaluate(root, configs, args.arm)


if __name__ == "__main__":
    main()
