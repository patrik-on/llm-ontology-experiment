"Internal transport, prompt preparation and persistence shared by the two current evaluation matrices. No standalone runner or legacy protocol."

from __future__ import annotations

from contextlib import contextmanager

from datetime import datetime, timezone

from io import BytesIO

import json

import os

from pathlib import Path

import re

from urllib.request import Request, urlopen

from uuid import uuid4

from llm_ontology.benchmarks import evaluation_direct as direct

from llm_ontology.benchmarks.evaluation_runtime import require_wsl

from llm_ontology.benchmarks.java_execution import (
    clean_env,
    evaluate_revision,
    file_sha256,
    run_process,
)

from llm_ontology.benchmarks.evaluation_generation import (
    build_dependency_identity,
    generate_ft,
    generate_rag,
    generation_failure_payload,
    hf_identity,
    load_eval_model,
)

from llm_ontology.inference.experiment_runner import RagExperimentRunner

from llm_ontology.inference.ollama_client import OllamaProvider

from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile

from llm_ontology.inference.prompting.testing_bodies_v1 import assemble, sha

from llm_ontology.inference.structured_output import TestingBodiesAnswer, parse_testing_bodies

from llm_ontology.retrieval.config import load_rag_config

from llm_ontology.retrieval.pipeline import VectorRetriever

ARMS = ("qwen_base", "ft_testing", "rag_single", "rag_multi")

PROTOCOL = "methods2test_systems_skills_v1"

OPTIONS = {"temperature": 0.0, "top_p": 0.9, "num_predict": 4096, "num_ctx": 32768, "seed": 42}


def now():
    return datetime.now(timezone.utc).isoformat()


def durable_json(path, payload, *, exclusive=False):
    """Never publish a partial replace; exclusive charge creation must not replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if exclusive else path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with target.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if not exclusive:
        os.replace(target, path)
    # Linux/WSL is the only experimental runtime.
    fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def file_lock(root, name, *, blocking=True):
    import fcntl

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / name).open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise RuntimeError("Run is already owned by another process") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_payload(payload):
    if (
        payload.get("options") != OPTIONS
        or payload.get("format") != TestingBodiesAnswer.model_json_schema()
    ):
        raise ValueError("Sampling/schema mismatch")
    if payload.get("model") != direct.MODELS["qwen_base"][0] or payload.get("stream") is not False:
        raise ValueError("Wrong model/transport")
    if not isinstance(payload.get("prompt"), str) or not payload["prompt"].strip():
        raise ValueError("Missing prompt")


class Ledger:
    """HTTP transport hook; the matrix owns validation and charging."""

    def __call__(self, request, **kwargs):
        base = "http://localhost:11434/api/"
        if request.full_url in [base + p for p in ["tags", "show", "version"]]:
            return urlopen(request, **kwargs)
        if request.full_url != base + "generate":
            raise ValueError("Unapproved model endpoint")
        payload = json.loads(request.data)
        validate_payload(payload)
        payload["keep_alive"] = 0
        self.charge(payload)
        request = Request(
            request.full_url,
            data=json.dumps(payload).encode(),
            headers=dict(request.headers),
            method="POST",
        )
        try:
            with urlopen(request, **kwargs) as response:
                raw = response.read()
            (self.out / "server_response.json").write_bytes(raw)
            server = json.loads(raw)
            if (
                not isinstance(server, dict)
                or server.get("error")
                or (not isinstance(server.get("response"), str))
            ):
                raise RuntimeError("Ollama API response envelope anomaly")
            (self.out / "raw.txt").write_text(server["response"], encoding="utf-8")
            return BytesIO(raw)
        except Exception as exc:
            if hasattr(exc, "read"):
                (self.out / "http_error.txt").write_bytes(exc.read())
            raise


class InfrastructureFailure(RuntimeError):
    """A provider/model-identity problem, never an ordinary output syntax failure."""


class _PreviewCaptured(Exception):
    pass


class PromptCapture:
    """Metadata requests allowed, generation endpoint is NEVER forwarded."""

    def __init__(self):
        self.payload = None

    def __call__(self, request, **kwargs):
        base = "http://localhost:11434/api/"
        if request.full_url in [base + p for p in ["tags", "show", "version"]]:
            return urlopen(request, **kwargs)
        if request.full_url != base + "generate":
            raise ValueError("Unapproved preview endpoint")
        payload = json.loads(request.data)
        validate_payload(payload)
        self.payload = payload
        raise _PreviewCaptured("Model-free prompt rendering: generation deliberately intercepted")


def _render_rag(c, case, out, arm, audit):
    capture = PromptCapture()
    try:
        generate_rag(c, case, out, arm, audit, body_profile=True, opener=capture)
    except Exception as exc:
        chain = exc
        while chain is not None and not isinstance(chain, _PreviewCaptured):
            chain = chain.__cause__
        if chain is None or capture.payload is None:
            raise
        durable_json(
            out / "preview_trace.json",
            {
                "generation_calls": 0,
                "intercepted_before_dispatch": True,
                "failure_metadata": getattr(exc, "failure_metadata", {}),
            },
        )
    else:
        raise RuntimeError("Preview unexpectedly completed a generation")
    durable_json(out / "request.json", capture.payload)
    return capture.payload["prompt"]


def _controls(root, c, selected):
    controls = {
        "pass": (
            "import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(4,2+2);} }",
            "passed",
        ),
        "fail": (
            "import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(5,2+2);} }",
            "assertion_failure",
        ),
        "empty": ("class Probe {}", "no_tests"),
    }
    for name, (source, expected) in controls.items():
        result = evaluate_revision(
            source,
            selected["cases"][0]["revision"],
            output=root / "controls" / name,
            java_home=c.java_home,
            junit_jar=c.junit_jar,
            junit_sha256=c.junit_sha256,
        )
        durable_json(root / "controls" / (name + ".json"), result)
        if result["status"] != expected:
            raise ValueError("Jupiter control failed: " + name)
    demo = root / "demo"
    demo.mkdir(parents=True)
    (demo / "Labels.java").write_text(profile.DEMO_PRODUCTION, encoding="utf-8")
    (demo / "GeneratedBodyTests.java").write_text(profile.demo_source(), encoding="utf-8")
    (demo / "block.txt").write_text(profile.DEMO_BLOCK, encoding="utf-8")
    classes = demo / "production-classes"
    classes.mkdir()
    result = run_process(
        [
            str(c.java_home / "bin/javac"),
            "-g",
            "-proc:none",
            "-d",
            str(classes),
            str(demo / "Labels.java"),
        ],
        demo,
        clean_env(demo / "home", c.java_home),
        30,
        demo / "compile.log",
    )
    if result.get("returncode") != 0:
        raise ValueError("Demo production failed")
    result = evaluate_revision(
        profile.demo_source(),
        {"bin_classes": str(classes), "dependencies": []},
        output=demo / "evaluation",
        java_home=c.java_home,
        junit_jar=c.junit_jar,
        junit_sha256=c.junit_sha256,
    )
    durable_json(demo / "control.json", result)
    if result["status"] != "passed" or result["console_summary"]["tests_started"] != 2:
        raise ValueError("Demo did not pass exactly two tests")


def _generate_direct(c, case, out, ledger, *, protocol_id=PROTOCOL):
    tokens = direct.counter()
    provider = OllamaProvider(
        model_name=direct.MODELS["qwen_base"][0],
        temperature=0,
        top_p=0.9,
        max_tokens=4096,
        context_window_tokens=32768,
        seed=42,
        timeout_seconds=c.generation_timeout_seconds,
        opener=ledger,
    )
    if provider.resolve_model_digest() != c.generation_model_digest:
        raise ValueError("Pinned Qwen generation digest changed")
    runner = RagExperimentRunner(
        retriever=VectorRetriever(direct.ForbiddenStore()),
        llm_provider=provider,
        token_counter=tokens,
        total_context_tokens=32768,
        reserved_output_tokens=4096,
        runtime_context_tokens=32768,
        fail_on_prompt_budget_exceeded=True,
        structured_retries=0,
        prompt_builder=profile.BodyPromptBuilder(),
        structured_answer_model=TestingBodiesAnswer,
    )
    exp = direct.experiment(out, "qwen_base", tokens).model_copy(
        update={
            "baseline_id": protocol_id,
            "dataset_version": case.metadata.get(
                "dataset_version", "methods2test-systems-skills-eval-v1"
            ),
        }
    )
    record = runner.run_case(exp, case)
    if record.generation_model_digest != c.generation_model_digest:
        raise InfrastructureFailure("Qwen digest changed during generation")
    return {"experiment_record": record.model_dump(mode="json")}


def _raw(out, generated=None, exc=None):
    path = out / "raw.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    attempts = (generated or {}).get("experiment_record", {}).get("structured_output_attempts", [])
    if not attempts and exc is not None:
        attempts = [a.model_dump(mode="json") for a in getattr(exc, "attempts", [])]
    return attempts[0].get("raw_response", "") if attempts else ""


def _infrastructure(out, raw):
    path = out / "server_response.json"
    if path.exists():
        try:
            server = read(path)
        except (ValueError, UnicodeError):
            return True
        if (
            not isinstance(server, dict)
            or server.get("error")
            or not isinstance(server.get("response"), str)
        ):
            return True
    return not isinstance(raw, str) or not raw.strip()


from llm_ontology.benchmarks.evaluation_runtime import load_config


def read(p):
    return json.loads(p.read_text())


def runtime():
    return load_config(Path("configs/benchmarks/java_evaluation_runtime_v1.yaml")).model_copy(
        update={"prompt_profile": None, "max_new_tokens": 4096}
    )


def ft_case(case):
    instruction = (
        case.instruction
        + "\n"
        + case.requirements
        + "\n"
        + case.project_context
        + "\nJSON schema: "
        + json.dumps(TestingBodiesAnswer.model_json_schema(), sort_keys=True)
    )
    return case.model_copy(update={"instruction": instruction})


__all__ = [
    "ARMS",
    "InfrastructureFailure",
    "Ledger",
    "OllamaProvider",
    "_controls",
    "_generate_direct",
    "_infrastructure",
    "_raw",
    "_render_rag",
    "assemble",
    "build_dependency_identity",
    "direct",
    "durable_json",
    "file_lock",
    "file_sha256",
    "ft_case",
    "generate_ft",
    "generate_rag",
    "generation_failure_payload",
    "hf_identity",
    "load_eval_model",
    "load_rag_config",
    "now",
    "parse_testing_bodies",
    "profile",
    "re",
    "read",
    "require_wsl",
    "runtime",
    "sha",
    "uuid4",
]
