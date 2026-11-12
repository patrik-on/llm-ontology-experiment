"""Explicit one-call GPT-OSS chat compatibility pilot, no retries or repairs."""
from __future__ import annotations
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from urllib.request import Request, urlopen
from llm_ontology.benchmarks import defects4j_direct_pilot as direct
from llm_ontology.benchmarks.defects4j import require_wsl, verify_prepared
from llm_ontology.benchmarks.defects4j_execution import evaluate_pair, file_sha256, write_json
from llm_ontology.benchmarks.defects4j_pilot import DEFAULT_CONFIG, load_protocol
from llm_ontology.benchmarks.defects4j_runner import generation_failure_payload
from llm_ontology.evaluation.run_layout import require_canonical_evaluation_path, validate_evaluation_run_id
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentRunner
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.inference.structured_output import TestingAnswer
from llm_ontology.retrieval.pipeline import VectorRetriever

PROTOCOL = "defects4j_gptoss_chat_single_full_class_v2"
PREVIOUS = Path("artifacts/evaluation/runs/direct-pure-fullclass-v2-20261112")
MODEL, DIGEST, THINK = direct.MODELS["gptoss20b"]


def read(path):
    return json.loads(path.read_text())


def inputs():
    raw, configs = load_protocol(DEFAULT_CONFIG)
    c = next(c for c in configs if c.case_id == "Lang-24")
    p = direct.OLD / "cases/Lang-24/prepared.json"
    if file_sha256(p) != read(direct.OLD / "freeze.json")["prepared"]["Lang-24"]:
        raise ValueError("Original prepared hash changed.")
    verify_prepared(read(p), c, prepared_path=p)
    case = PREVIOUS / "cases/Lang-24/case.json"
    if file_sha256(case) != read(PREVIOUS / "freeze.json")["cases"]["Lang-24"]:
        raise ValueError("Original case hash changed.")
    pins = direct.current_pins(raw, [c])
    return c, p, case, json.loads(json.dumps(pins))


class SingleRequestLedger:
    """Atomic exclusive root dispatch: HTTP failures consume the sole call."""
    def __init__(self, root):
        self.root = root

    def __call__(self, request, **kwargs):
        if request.full_url in ["http://localhost:11434/api/" + p for p in ("tags", "show", "version")]:
            return urlopen(request, **kwargs)
        if request.full_url != "http://localhost:11434/api/chat":
            raise ValueError("Only declared WSL chat generation permitted.")
        payload = json.loads(request.data)
        prior = read(PREVIOUS / "cases/Lang-24/predictions/gptoss20b/dispatch.json")["request"]
        expected = {k: v for k, v in prior.items() if k != "prompt"}
        expected["messages"] = [{"role": "user", "content": prior["prompt"]}]
        payload["keep_alive"] = 0
        if payload != expected:
            raise ValueError("Visible prompt/schema/decoding changed unexpectedly.")
        encoded = json.dumps(payload).encode()
        request = Request(request.full_url, data=encoded, headers=dict(request.headers), method="POST")
        with (self.root / "dispatch.json").open("x") as handle:
            json.dump({"charged_to_budget": True, "maximum": 1, "endpoint": request.full_url,
                       "client_transport": "OllamaProvider/chat/urllib", "request": payload,
                       "request_sha256": hashlib.sha256(encoded).hexdigest()}, handle, indent=2)
        try:
            response = urlopen(request, **kwargs)
            raw = response.read()
            response.close()
            (self.root / "server_response.json").write_bytes(raw)
        except Exception as exc:
            if hasattr(exc, "read"):
                (self.root / "http_error.txt").write_bytes(exc.read())
            raise
        message = json.loads(raw).get("message", {})
        (self.root / "content.txt").write_text(message.get("content", ""))
        (self.root / "thinking.private.txt").write_text(message.get("thinking", ""))
        return BytesIO(raw)


def generate(root):
    (root / "generation_reserved").mkdir(exist_ok=False)
    tokens = direct.counter()
    provider = OllamaProvider(model_name=MODEL, transport="chat", think=THINK,
        max_tokens=4096, context_window_tokens=32768, temperature=0, top_p=.9, seed=42,
        timeout_seconds=1800, opener=SingleRequestLedger(root))
    if provider.resolve_model_digest() != DIGEST:
        raise ValueError("Installed model changed.")
    runner = RagExperimentRunner(retriever=VectorRetriever(direct.ForbiddenStore()),
        llm_provider=provider, token_counter=tokens, total_context_tokens=32768,
        reserved_output_tokens=4096, safety_margin_tokens=256, runtime_context_tokens=32768,
        fail_on_prompt_budget_exceeded=True, structured_retries=0)
    config = direct.experiment(root, "gptoss20b", tokens).model_copy(update={"baseline_id": PROTOCOL})
    case = ExperimentCase.model_validate_json((root / "case.json").read_text())
    try:
        record = runner.run_case(config, case)
        source = TestingAnswer.model_validate_json(record.response).generated_tests
        (root / "generated.java").write_text(source)
        write_json(root / "generation.json", {"source": source,
            "source_sha256": file_sha256(root / "generated.java"),
            "experiment_record": record.model_dump(mode="json")})
        print(json.dumps({"schema_valid": True, "source_sha256": file_sha256(root / "generated.java")}), flush=True)
    except Exception as exc:
        write_json(root / "failure.json", generation_failure_payload(exc,
            case_sha256=file_sha256(root / "case.json"), arm="gptoss20b_chat"))
        print(json.dumps({"generation_failed": True, "error_type": type(exc).__name__}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "generate", "evaluate"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--reviewed-source-sha256")
    args = parser.parse_args(argv)
    require_wsl()
    validate_evaluation_run_id(args.run_id)
    root = require_canonical_evaluation_path(Path("artifacts/evaluation/runs") / args.run_id).resolve()
    c, p, case, pins = inputs()
    if args.action == "freeze":
        root.mkdir(parents=True, exist_ok=False)
        provider = OllamaProvider(model_name=MODEL, transport="chat")
        if provider.resolve_model_digest() != DIGEST:
            raise ValueError("Installed GPT-OSS identity mismatch.")
        show = provider.describe_model()
        if "thinking" not in show.get("capabilities", []) or "<|start|>" not in show.get("template", ""):
            raise ValueError("Expected thinking/Harmony metadata unavailable.")
        write_json(root / "model.json", show)
        write_json(root / "server_version.json", provider._request_json("/api/version", None, method="GET"))
        (root / "case.json").write_bytes(case.read_bytes())
        write_json(root / "schema.json", TestingAnswer.model_json_schema())
        write_json(root / "job_plan.json", {"protocol": PROTOCOL, "max_actual_generation_calls": 1,
            "case": "Lang-24", "retries": 0, "repairs": 0, "explicit_system_messages": [],
            "model_system": show.get("system", ""), "messages": "one exact canonical user prompt",
            "server_template_sha256": hashlib.sha256(show.get("template", "").encode()).hexdigest(),
            "reasoning": "low; server-internal staged decoding possible; token split unavailable"})
        write_json(root / "freeze.json", {"pins": pins, "prepared_sha256": file_sha256(p),
            **{name: file_sha256(root / name) for name in ("case.json", "schema.json", "model.json")}})
        return
    frozen = read(root / "freeze.json")
    if frozen["pins"] != pins or frozen["prepared_sha256"] != file_sha256(p):
        raise ValueError("Frozen implementation/config/prepared input changed.")
    for name in ("case.json", "schema.json", "model.json"):
        if file_sha256(root / name) != frozen[name]:
            raise ValueError("Frozen input changed: " + name)
    if args.action == "generate":
        if not args.diagnostic:
            raise ValueError("Explicit --diagnostic required.")
        generate(root)
    else:
        generated = read(root / "generation.json")
        if file_sha256(root / "generated.java") != generated["source_sha256"] or args.reviewed_source_sha256 != generated["source_sha256"]:
            raise ValueError("Source changed or missing matching review hash; no repairs.")
        write_json(root / "review.json", {"reviewed_local_execution": True, "source_sha256": args.reviewed_source_sha256})
        result = evaluate_pair(generated["source"], read(p), output=root / "metrics", java_home=c.java_home,
            junit_jar=c.junit_jar, junit_sha256=c.junit_sha256, timeout=c.timeout_seconds, repeats=2)
        print(json.dumps({"fixed_pass": result["fixed_pass"], "detected_bug": result["detected_bug"],
                          "statuses": result["statuses"]}), flush=True)


if __name__ == "__main__":
    main()
