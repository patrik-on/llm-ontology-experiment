"""Thin benchmark composition: existing HF inference and canonical RAG runner.

These are explicitly different prompt/backend contracts, not a causal FT-vs-RAG
ablation. The fixed focal input and executable evaluator are shared.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from llm_ontology.benchmarks.defects4j import (
    PROTOCOL, Defects4JConfig, audit_leakage, load_config, prepare, require_wsl, verify_prepared,
)
from llm_ontology.benchmarks.defects4j_execution import (
    D4J_COMMIT, evaluate_pair, evaluate_revision, file_sha256, write_json,
)
from llm_ontology.core.config import read_yaml
from llm_ontology.evaluation.run_layout import EvaluationRunLayout
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentConfig, RagExperimentRunner
from llm_ontology.evaluation.inference_eval import generate_prediction, load_eval_model, selected_models
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.structured_output import TestingAnswer
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.factory import create_llm_provider, create_vector_store
from llm_ontology.retrieval.models import RetrievalMode
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter

ARMS = ("ft_testing", "rag_single", "rag_multi")


def hf_identity(config: Defects4JConfig, *, hashes: bool = True) -> dict[str, Any]:
    models = read_yaml(config.hf_models_config)
    model = selected_models(models, config.hf_model_name)[0]
    root = Path(model["model_path"]).expanduser().resolve()
    adapter = Path(model["adapter_path"]).expanduser().resolve()
    if not root.is_dir() or not adapter.is_dir():
        raise FileNotFoundError("Local model or testing specialist adapter is absent.")
    files = [root / name for name in ("config.json", "tokenizer_config.json", "tokenizer.json")]
    shard_index = root / "model.safetensors.index.json"
    if shard_index.exists():
        files.append(shard_index)
        shard_map = json.loads(shard_index.read_text())["weight_map"]
        for shard in sorted(set(shard_map.values())):
            path = (root / shard).resolve()
            path.relative_to(root)
            files.append(path)
    else:
        files.append(root / "model.safetensors")
    provenance = adapter.parents[1] / "results"
    files.extend([adapter / "adapter_config.json", adapter / "adapter_model.safetensors",
                  provenance / "config_snapshot.yaml", provenance / "training_summary.json"])
    training = json.loads((provenance / "training_summary.json").read_text())
    if Path(training["train_file"]) not in config.training_sources:
        raise ValueError("Leakage inputs do not include the specialist training-summary source.")
    identities = {}
    for path in files:
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"Incomplete local model: {path}")
        identities[str(path)] = {"bytes": path.stat().st_size,
                                 "sha256": file_sha256(path) if hashes else "not_computed"}
    return {"model": model, "inference": models["inference"], "files": identities,
            "prompt_contract": "instruction-v1-raw-java-jupiter-request",
            "output_contract": "raw-java-only-no-semantic-repair"}


def readiness(config: Defects4JConfig) -> dict[str, Any]:
    from llm_ontology.ui.service import EnvironmentStatusService
    import subprocess
    checks: dict[str, Any] = {}
    try:
        require_wsl()
        checks["runtime"] = "WSL"
    except RuntimeError as exc:
        checks["runtime"] = str(exc)
    for name, call in {
        "hf": lambda: hf_identity(config, hashes=False),
        "rag": lambda: EnvironmentStatusService(load_rag_config(config.retrieval_config)).inspect().model_dump(mode="json"),
        "defects4j": lambda: subprocess.check_output(
            ["git", "-C", str(config.defects4j_home), "rev-parse", "HEAD"], text=True).strip(),
        "java": lambda: subprocess.check_output([str(config.java_home / "bin/java"), "-version"],
                                                stderr=subprocess.STDOUT, text=True),
        "junit": lambda: file_sha256(config.junit_jar),
    }.items():
        try:
            checks[name] = call()
        except Exception as exc:
            checks[name] = {"error": str(exc)}
    checks["model_free_assets_ready"] = (
        checks["runtime"] == "WSL" and checks["defects4j"] == D4J_COMMIT
        and isinstance(checks["java"], str) and 'version "11.' in checks["java"]
        and checks["junit"] == config.junit_sha256)
    checks["scientific_ready"] = False
    checks["limitations"] = ["Readiness is not successful compilation/model loading.",
                              "Leakage audit and evaluator controls required separately.",
                              "No OS security sandbox: all local runs diagnostic-only."]
    return checks


def generate_ft(config: Defects4JConfig, case: ExperimentCase, output: Path) -> dict[str, Any]:
    import torch
    # Local paths only, no tokenizer/model/adapter downloads or remote custom code.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    identity = hf_identity(config)
    write_json(output / "model_identity.json", identity)
    inference = {**identity["inference"], "local_files_only": True, "trust_remote_code": False}
    prompt = format_inference_prompt(case.instruction, case.input_text)
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    model, tokenizer = load_eval_model(identity["model"], inference)
    try:
        prompt_tokens = len(tokenizer(prompt)["input_ids"])
        if prompt_tokens + config.max_new_tokens + 256 > 32768:
            raise ValueError("FT prompt exceeds declared context; do not silently truncate.")
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)
        with torch.inference_mode():
            prediction, generation = generate_prediction(
                model, tokenizer, "testing", case.instruction, case.input_text,
                {"max_new_tokens": config.max_new_tokens, "do_sample": False,
                 "top_p": 0.9, "repetition_penalty": 1.0})
        (output / "raw.txt").write_text(prediction, encoding="utf-8")
        # Only an exact surrounding Markdown fence may be removed; never rewrite Java/JUnit4.
        source = prediction.strip()
        if chr(0) in source:
            raise ValueError("Invalid NUL output.")
        if source.startswith("~~~"):
            raise ValueError("Unexpected non-Java output.")
        if source.startswith("" + chr(96) * 3):
            lines = source.splitlines()
            if lines[-1].strip() != chr(96) * 3:
                raise ValueError("Unclosed output fence; truncated generation.")
            source = "\n".join(lines[1:-1]).strip()
        return {"source": source, "prompt_contract": identity["prompt_contract"],
                "model_identity": identity, "generation": generation, "prompt_tokens": prompt_tokens,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    finally:
        del model, tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def generate_rag(config: Defects4JConfig, case: ExperimentCase, output: Path,
                 arm: str, audit: dict[str, Any]) -> dict[str, Any]:
    rag = load_rag_config(config.retrieval_config)
    if (rag.runtime.environment != "wsl" or rag.llm.base_url != "http://localhost:11434"
            or rag.embeddings.base_url != "http://localhost:11434"):
        raise ValueError("Only the canonical WSL-local Ollama endpoint is allowed.")
    if rag.llm.provider != "ollama" or rag.embeddings.provider != "ollama":
        raise ValueError("This bounded protocol requires existing local Ollama providers.")
    if not (Path(rag.vector_store.persist_path) / "chroma.sqlite3").is_file():
        raise FileNotFoundError("Existing index is absent; this runner never initializes/rebuilds it.")
    # Reuse the local HF tokenizer with a content-addressed identity, no Hub access.
    identity = hf_identity(config, hashes=False)
    tokenizer_path = Path(identity["model"]["model_path"])
    tokenizer_digest = file_sha256(tokenizer_path / "tokenizer.json")
    counter = HuggingFaceTokenCounter(model_identifier=str(tokenizer_path), model_revision=tokenizer_digest)
    provider = create_llm_provider(rag.llm.model_copy(update={"max_tokens": config.max_new_tokens}))
    generation_digest = provider.resolve_model_digest()
    if generation_digest != config.generation_model_digest:
        raise ValueError("Pinned local generation model digest changed.")
    write_json(output / "ollama_model.json", provider.describe_model())
    mode = RetrievalMode.SINGLE_COLLECTION_RAG if arm == "rag_single" else RetrievalMode.MULTI_COLLECTION_RAG
    manifests = [json.loads(p.read_text()) for p in
                 sorted((Path(rag.vector_store.persist_path) / "manifests").glob("*.json"))]
    embedding_digests = {m["embedding_model_digest"] for m in manifests}
    if len(embedding_digests) != 1:
        raise ValueError("Incoherent embedding identities.")
    embedding_digest = next(iter(embedding_digests))
    if embedding_digest != config.embedding_model_digest:
        raise ValueError("Pinned embedding model/index digest changed.")
    exp = RagExperimentConfig(
        enabled=True, baseline_id=PROTOCOL, requested_task="testing", retrieval_mode=mode,
        collection="mixed" if arm == "rag_single" else None,
        collections=[] if arm == "rag_single" else ["testing_db", "refactoring_db"],
        dataset_version="defects4j-3.0.1-canary", embedding_model=rag.embeddings.model,
        embedding_revision=embedding_digest, llm_model=rag.llm.model,
        generation_max_tokens=config.max_new_tokens,
        dataset_manifest_ids=sorted({d for m in manifests for d in m["dataset_manifests"]}),
        top_k=rag.retrieval.top_k, per_collection_top_k=rag.retrieval.per_collection_top_k,
        retrieval_query_strategy=rag.retrieval.query_strategy,
        retrieval_reranking_strategy=rag.retrieval.reranking_strategy,
        retrieval_candidate_pool_size=rag.retrieval.candidate_pool_size,
        tokenizer_model=counter.model_identifier, tokenizer_revision=counter.model_revision,
        total_context_tokens=32768, reserved_output_tokens=config.max_new_tokens,
        safety_margin_tokens=256, retrieval_token_budget=12000,
        runtime_context_tokens=32768, fail_on_prompt_budget_exceeded=True,
        results_path=output / "experiment.jsonl", prompt_artifacts_dir=output / "prompts")
    runner = RagExperimentRunner(
        retriever=VectorRetriever(create_vector_store(rag)), llm_provider=provider,
        token_counter=counter, total_context_tokens=32768,
        reserved_output_tokens=config.max_new_tokens, safety_margin_tokens=256,
        retrieval_token_budget=12000, runtime_context_tokens=32768,
        fail_on_prompt_budget_exceeded=True, structured_retries=0)
    record = runner.run_case(exp, case)
    if record.generation_model_digest != generation_digest:
        raise ValueError("Generation model digest changed during run.")
    source = TestingAnswer.model_validate_json(record.response).generated_tests
    return {"source": source, "prompt_contract": "canonical-json-v2-junit5",
            "experiment_record": record.model_dump(mode="json"), "leakage_audit": audit}


def canary(config: Defects4JConfig, prepared: dict[str, Any], output: Path) -> dict[str, Any]:
    # Evaluator-only reference: never passed into ExperimentCase/retrieval/training.
    header = "import org.junit.jupiter.api.*; import static org.junit.jupiter.api.Assertions.*; "
    controls = {
        "pass": (header + "class Probe { @Test void t() { assertTrue(true); } }", "passed"),
        "assertion": (header + "class Probe { @Test void t() { assertTrue(false); } }", "assertion_failure"),
        "empty": (header + "class Probe {}", "no_tests"),
        "disabled": (header + "class Probe { @Disabled @Test void t() {} }", "no_tests"),
        "compile": (header + "class Probe { @Test void t() { missing(); } }", "compile_failure"),
        "runtime": (header + "class Probe { @Test void t() { throw new RuntimeException(); } }", "execution_error"),
        "timeout": (header + "class Probe { @Test void t() { while(true) {} } }", "timeout"),
    }
    results = {}
    for name, (source, expected) in controls.items():
        result = evaluate_revision(source, prepared["fixed"], output=output / name,
            java_home=config.java_home, junit_jar=config.junit_jar,
            junit_sha256=config.junit_sha256, timeout=3 if name == "timeout" else config.timeout_seconds)
        results[name] = {"expected": expected, "actual": result["status"],
                         "ok": result["status"] == expected}
    reference = header + (
        "class Lang24Canary { @Test void decimalCannotHaveLongSuffix() { "
        'assertFalse(org.apache.commons.lang3.math.NumberUtils.isNumber("1.1L")); } }')
    pair = evaluate_pair(reference, prepared, output=output / "fault-pair",
        java_home=config.java_home, junit_jar=config.junit_jar, junit_sha256=config.junit_sha256,
        timeout=config.timeout_seconds, repeats=config.repeats)
    summary = {"controls": results, "real_fault_detected": pair["detected_bug"],
               "passed": all(x["ok"] for x in results.values()) and pair["detected_bug"],
               "model_calls": 0, "diagnostic_only": True}
    write_json(output / "canary.json", summary)
    return summary


def report(root: Path) -> dict[str, Any]:
    arms = {}
    for arm in ARMS:
        prediction = root / "predictions" / arm
        attempted = int(prediction.exists())
        generated = int((prediction / "generation.json").is_file())
        evaluated = root / "metrics" / arm / "evaluation.json"
        result = json.loads(evaluated.read_text()) if evaluated.exists() else {}
        fixed = result.get("outcomes", {}).get("fixed", [])
        compiled = bool(fixed) and all(r.get("compile", {}).get("status") == "completed"
                                      and r["compile"].get("returncode") == 0 for r in fixed)
        executed = compiled and all(r.get("discovery", {}).get("executed", 0) > 0 for r in fixed)
        passed = bool(result.get("fixed_pass"))
        detected = bool(result.get("detected_bug"))
        arms[arm] = {"attempts": attempted, "generated": generated, "evaluated": int(bool(result)),
                     "fixed_compiled": int(compiled), "fixed_nonempty_executed": int(executed),
                     "fixed_passed": int(passed), "real_bug_detected": int(detected),
                     "unconditional_compilation_rate": int(compiled)/attempted if attempted else None,
                     "unconditional_nonempty_rate": int(executed)/attempted if attempted else None,
                     "unconditional_fixed_pass_rate": int(passed)/attempted if attempted else None,
                     "unconditional_detection_rate": int(detected)/attempted if attempted else None,
                     "conditional_fixed_pass_rate": int(passed) if executed else None,
                     "conditional_detection_rate": int(detected) if passed else None,
                     "statuses": result.get("statuses"),
                     "generation_failure": json.loads((prediction / "failure.json").read_text())
                     if (prediction / "failure.json").exists() else None}
    return {"protocol": PROTOCOL, "diagnostic_only": True, "scientific_scores": False,
            "arms": arms, "coverage": "not_measured", "cases": 1,
            "methodology": "identical fixed focal input and evaluator; different declared prompts/backends"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded Defects4J FT/RAG testing integration")
    parser.add_argument("action", choices=("dry-run", "readiness", "prepare", "audit", "canary", "generate", "evaluate", "report"))
    parser.add_argument("--config", type=Path, default=Path("configs/benchmarks/defects4j_jupiter_v1.yaml"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", choices=ARMS, default="ft_testing")
    parser.add_argument("--diagnostic", action="store_true", help="Explicitly allow flagged diagnostic generation")
    parser.add_argument("--reviewed-local-execution", action="store_true",
                        help="Acknowledge reviewed subject/generated code; no OS sandbox")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    layout = EvaluationRunLayout(args.run_id)
    if args.action == "dry-run":
        print(json.dumps({"protocol": PROTOCOL, "case": config.case_id, "arms": ARMS,
                          "config": config.model_dump(mode="json"), "output": str(layout.root),
                          "model_calls": 0, "writes": 0, "scientific_ready": False}, indent=2))
        return 0
    require_wsl()
    identity = config.model_dump(mode="json")
    code_root = Path(__file__).parent
    dependency_identity = {str(p): file_sha256(p) for p in (config.retrieval_config, config.hf_models_config,
        code_root / "defects4j.py", code_root / "defects4j_execution.py", Path(__file__))}
    if layout.root.exists() and any(layout.root.iterdir()) and not layout.manifest_path.exists():
        raise FileExistsError("Nonempty run directory without a manifest; choose a new run_id.")
    if layout.manifest_path.exists():
        old = json.loads(layout.manifest_path.read_text())["metadata"]["config"]
        previous_dependencies = json.loads(layout.manifest_path.read_text())["metadata"].get("dependencies")
        if old != identity or previous_dependencies != dependency_identity:
            raise ValueError("Run/config mismatch: choose a new run_id; no overwrite.")
    layout.write_manifest(status="in_progress", metadata={"config": identity, "dependencies": dependency_identity, "protocol": PROTOCOL,
        "diagnostic_only": True, "methodology": "shared case/evaluator, different declared prompts/backends"})
    root = layout.root.resolve()
    prepared_path = root / "prepared.json"
    try:
        if args.action == "readiness":
            result = readiness(config)
            write_json(root / "readiness.json", result)
            print(json.dumps(result, indent=2))
            return 0 if result["model_free_assets_ready"] else 2
        if args.action in ("prepare", "canary", "evaluate") and not args.reviewed_local_execution:
            raise ValueError("Review build/generated code first, then pass --reviewed-local-execution.")
        if args.action == "prepare":
            if prepared_path.exists():
                raise FileExistsError("Preparation already exists; never overwrite it.")
            result = prepare(config, prepared_path)
            print(f"Prepared {result['case']['case_id']}; no model calls.")
            return 0
        prepared = json.loads(prepared_path.read_text())
        verify_prepared(prepared, config)
        rag = load_rag_config(config.retrieval_config)
        audit_path = root / "leakage_audit.json"
        if args.action in ("audit", "generate"):
            audit = audit_leakage(config, prepared, Path(rag.vector_store.persist_path))
            if audit_path.exists() and args.action == "generate":
                if json.loads(audit_path.read_text()) != audit:
                    raise ValueError("Training/index identities changed after audit.")
            write_json(audit_path, audit)
            if args.action == "audit":
                print(json.dumps(audit, indent=2))
                return 0 if audit["scientifically_clean"] else 2
        if args.action == "canary":
            result = canary(config, prepared, root / "canary")
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 2
        if args.action == "report":
            result = report(root)
            write_json(root / "reports/summary.json", result)
            print(json.dumps(result, indent=2))
            return 0
        if args.action == "generate":
            if not args.diagnostic:
                raise ValueError("Only diagnostic generation is enabled until a sandbox and clean lineage exist.")
            control = json.loads((root / "canary/canary.json").read_text())
            if not control["passed"]:
                raise ValueError("Real evaluator controls must pass before model calls.")
            out = root / "predictions" / args.arm
            out.mkdir(parents=True, exist_ok=False)
            case = ExperimentCase.model_validate(prepared["case"])
            started = perf_counter()
            try:
                generated = (generate_ft(config, case, out) if args.arm == "ft_testing" else
                             generate_rag(config, case, out, args.arm, audit))
                generated.update({"case_sha256": prepared["case_sha256"], "arm": args.arm,
                                  "diagnostic_only": True, "duration_seconds": perf_counter()-started})
                (out / "generated.java").write_text(generated["source"], encoding="utf-8")
                generated["source_sha256"] = file_sha256(out / "generated.java")
                write_json(out / "generation.json", generated)
                print(f"Generated {args.arm}; diagnostic only; inspect {out / 'generated.java'} before execution.")
            except Exception as exc:
                write_json(out / "failure.json", {"status": "generation_failure", "error": str(exc),
                    "case_sha256": prepared["case_sha256"], "arm": args.arm, "diagnostic_only": True})
                raise
            return 0
        if args.action == "evaluate":
            out = root / "predictions" / args.arm
            generation = json.loads((out / "generation.json").read_text())
            source = (out / "generated.java").read_text()
            if generation["case_sha256"] != prepared["case_sha256"] or file_sha256(out / "generated.java") != generation["source_sha256"]:
                raise ValueError("Generated case/source changed; no silent repair.")
            result = evaluate_pair(source, prepared, output=root / "metrics" / args.arm,
                java_home=config.java_home, junit_jar=config.junit_jar, junit_sha256=config.junit_sha256,
                timeout=config.timeout_seconds, repeats=config.repeats)
            print(json.dumps({key: result[key] for key in ("fixed_pass", "detected_bug", "statuses")}, indent=2))
            return 0
    except Exception as exc:
        layout.write_manifest(status="blocked", metadata={"last_action": args.action, "error": str(exc)})
        raise
    finally:
        # Per-stage files are authoritative; this is not a final experimental success gate.
        if sys.exc_info()[0] is None:
            layout.write_manifest(status=f"{args.action}_completed", metadata={"last_action": args.action, "error": None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
