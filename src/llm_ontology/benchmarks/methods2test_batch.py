"""Opt-in 100-case / 400-cell dispatch, leaving the frozen five-case pilot intact.

Only freeze/verify are model-free. Freeze renders the *actual* RAG prompts by
intercepting the existing runner immediately before its generation HTTP request;
retrieval/embedding requests are not generation calls. No synthetic model answer
is supplied. All 400 prompts exist before the first charged generation.

A process-wide run flock serializes GPU ownership. Under a separate budget flock,
exclusive, fsynced dispatch files are the authoritative charges (including crashes
between charge and request). The global ledger/progress are reconstructible views.
An unfinished charge is never retried and is reported as interrupted/unresolved.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
from time import perf_counter
from urllib.request import Request, urlopen
from uuid import uuid4

from llm_ontology.benchmarks import defects4j_direct_pilot as direct
from llm_ontology.benchmarks import methods2test_pilot as pilot
from llm_ontology.benchmarks.defects4j import require_wsl
from llm_ontology.benchmarks.defects4j_execution import (
    clean_env, evaluate_revision, file_sha256, run_process,
)
from llm_ontology.benchmarks.defects4j_runner import (
    build_dependency_identity, generate_ft, generate_rag, generation_failure_payload,
    hf_identity, load_eval_model,
)
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentRunner
from llm_ontology.inference.ollama_client import OllamaProvider
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.prompting.testing_bodies_v1 import assemble, sha
from llm_ontology.inference.structured_output import (
    StructuredOutputError, TestingBodiesAnswer, parse_testing_bodies,
)
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.pipeline import VectorRetriever

ARMS = pilot.ARMS
CONFIG = Path("configs/benchmarks/methods2test_eval_hundred_v1.json")
PROTOCOL = "methods2test_eval_hundred_v1"
CASE_COUNT = 100
MAX_CALLS = 400
OPTIONS = {"temperature": 0.0, "top_p": .9, "num_predict": 4096,
           "num_ctx": 32768, "seed": 42}
read = pilot.read
runtime = pilot.runtime
ft_case = pilot.ft_case


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


def selection(root):
    selected = read(Path(root) / "selection.json")
    ids, cases = selected.get("ids", []), selected.get("cases", [])
    if (len(ids) != CASE_COUNT or len(set(ids)) != CASE_COUNT
            or len(cases) != CASE_COUNT or [c.get("id") for c in cases] != ids):
        raise ValueError("selection.json requires exactly 100 distinct, matching ordered IDs/cases")
    if any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", i)
           or i in {".", ".."} for i in ids):
        raise ValueError("Unsafe case ID")
    return selected


def protocol():
    plan = read(CONFIG)
    expected = {"protocol": PROTOCOL, "cases": CASE_COUNT,
                "max_actual_generation_calls": MAX_CALLS, "attempts_per_cell": 1,
                "retries": 0, "repairs": 0, "max_new_tokens": 4096,
                "seed": 42, "temperature": 0, "top_p": .9,
                "context_window_tokens": 32768, "prompt_profile": "testing-bodies-one-shot-v2",
                "indexing_allowed": False, "official_split": "eval"}
    for key, value in expected.items():
        if plan.get(key) != value:
            raise ValueError("Batch protocol mismatch: " + key)
    if plan.get("arms") != list(ARMS):
        raise ValueError("Four fixed arms required")
    return plan


def output_dir(root, ident, arm):
    return Path(root) / "cases" / ident / "predictions" / arm


def _dispatches(root):
    paths = list(Path(root).glob("cases/*/predictions/*/dispatch.json"))
    allowed = set(selection(root)["ids"])
    for path in paths:
        if path.parents[2].name not in allowed or path.parent.name not in ARMS:
            raise ValueError("Unplanned dispatch in budget ledger: " + str(path))
    if len(paths) > MAX_CALLS:
        raise RuntimeError("400-cell budget already exceeded")
    return paths


def _progress(root, *, active_arm=None, running=False):
    """Caller holds budget flock; never infer completion from a charge alone."""
    root = Path(root)
    old = read(root / "progress.json") if (root / "progress.json").exists() else {}
    ids = selection(root)["ids"]
    cells, totals = {}, {"charged": 0, "completed": 0, "assembled": 0,
                        "model_output_failure": 0, "infrastructure_failure": 0,
                        "interrupted_unresolved": 0, "pending": 0, "blocked": 0,
                        "pre_dispatch_failure": 0, "in_flight": 0}
    dispatches = _dispatches(root)
    charged_paths = set(dispatches)
    for arm in ARMS:
        stopped = (root / (arm + "-stop.json")).exists()
        for ident in ids:
            out = output_dir(root, ident, arm)
            charged = out / "dispatch.json" in charged_paths
            completion = out / "completion.json"
            if completion.exists():
                result = read(completion)
                status = result["status"]
                totals["completed"] += 1
                totals[status] = totals.get(status, 0) + 1
            elif charged:
                status = "in_flight" if running and arm == active_arm and not (out / "interrupted.json").exists() else "interrupted_unresolved"
                totals[status] += 1
            else:
                status = "blocked" if stopped else "pending"
                totals[status] += 1
            totals["charged"] += int(charged)
            cells[ident + "/" + arm] = {"status": status, "charged": charged}
    ledger = {"maximum": MAX_CALLS, "charged": len(dispatches),
              "cells": sorted(str(p.relative_to(root)) for p in dispatches)}
    durable_json(root / "dispatch_ledger.json", ledger)
    progress = {"protocol": PROTOCOL, "started_at": old.get("started_at", now()),
                "updated_at": now(), "running": running, "active_arm": active_arm,
                "maximum": MAX_CALLS, "counts": totals,
                "remaining_budget": MAX_CALLS - totals["charged"],
                "remaining": totals["pending"], "cells": cells}
    durable_json(root / "progress.json", progress)
    return progress


def progress(root, **kwargs):
    with file_lock(root, ".budget.lock"):
        return _progress(root, **kwargs)


def validate_payload(payload):
    if payload.get("options") != OPTIONS or payload.get("format") != TestingBodiesAnswer.model_json_schema():
        raise ValueError("Sampling/schema mismatch")
    if payload.get("model") != direct.MODELS["qwen_base"][0] or payload.get("stream") is not False:
        raise ValueError("Wrong model/transport")
    if not isinstance(payload.get("prompt"), str) or not payload["prompt"].strip():
        raise ValueError("Missing prompt")


class Ledger:
    """Charge immediately before the existing provider dispatches, exactly once."""
    def __init__(self, root, ident, arm):
        self.root, self.ident, self.arm = Path(root), ident, arm
        if ident not in selection(root)["ids"] or arm not in ARMS:
            raise ValueError("Unplanned cell")
        self.out = output_dir(root, ident, arm)
        self.dispatch_time = None

    def charge(self, payload):
        expected = (self.root / "cases" / self.ident / "frozen_prompts" / self.arm / "prompt.txt").read_text(encoding="utf-8")
        if payload.get("prompt") != expected:
            raise ValueError("Actual prompt differs from pre-dispatch frozen prompt")
        with file_lock(self.root, ".budget.lock"):
            if (self.out / "dispatch.json").exists():
                raise FileExistsError("Cell already charged; retry forbidden")
            if (self.out / "completion.json").exists() or (self.root / (self.arm + "-stop.json")).exists():
                raise RuntimeError("Cell completed or arm fail-stopped")
            if len(_dispatches(self.root)) >= MAX_CALLS:
                raise RuntimeError("400-call global cap reached")
            durable_json(self.out / "dispatch.json", {
                "charged_to_budget": True, "id": self.ident, "arm": self.arm,
                "request": payload, "maximum": MAX_CALLS, "charged_at": now(),
            }, exclusive=True)
            self.dispatch_time = perf_counter()
            _progress(self.root, active_arm=self.arm, running=True)

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
        request = Request(request.full_url, data=json.dumps(payload).encode(),
                          headers=dict(request.headers), method="POST")
        try:
            with urlopen(request, **kwargs) as response:
                raw = response.read()
            (self.out / "server_response.json").write_bytes(raw)
            server = json.loads(raw)
            if not isinstance(server, dict) or server.get("error") or not isinstance(server.get("response"), str):
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
        durable_json(out / "preview_trace.json", {
            "generation_calls": 0, "intercepted_before_dispatch": True,
            "failure_metadata": getattr(exc, "failure_metadata", {}),
        })
    else:
        raise RuntimeError("Preview unexpectedly completed a generation")
    durable_json(out / "request.json", capture.payload)
    return capture.payload["prompt"]


def _controls(root, c, selected):
    controls = {
        "pass": ('import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(4,2+2);} }', "passed"),
        "fail": ('import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; class Probe { @Test void t(){assertEquals(5,2+2);} }', "assertion_failure"),
        "empty": ('class Probe {}', "no_tests"),
    }
    for name, (source, expected) in controls.items():
        result = evaluate_revision(source, selected["cases"][0]["revision"],
                                   output=root / "controls" / name,
                                   java_home=c.java_home, junit_jar=c.junit_jar,
                                   junit_sha256=c.junit_sha256)
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
    result = run_process([str(c.java_home / "bin/javac"), "-g", "-proc:none", "-d", str(classes), str(demo / "Labels.java")],
                         demo, clean_env(demo / "home", c.java_home), 30, demo / "compile.log")
    if result.get("returncode") != 0:
        raise ValueError("Demo production failed")
    result = evaluate_revision(profile.demo_source(), {"bin_classes": str(classes), "dependencies": []},
                               output=demo / "evaluation", java_home=c.java_home,
                               junit_jar=c.junit_jar, junit_sha256=c.junit_sha256)
    durable_json(demo / "control.json", result)
    if result["status"] != "passed" or result["console_summary"]["tests_started"] != 2:
        raise ValueError("Demo did not pass exactly two tests")


def freeze(root):
    root = Path(root).resolve()
    with file_lock(root, ".run.lock", blocking=False):
        if (root / "freeze.json").exists():
            raise FileExistsError("Already frozen")
        if list(root.glob("cases/*/predictions/*/dispatch.json")):
            raise ValueError("Cannot freeze after a generation charge")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        selected, plan, c = selection(root), protocol(), runtime()
        _controls(root, c, selected)
        # This expensive identity is computed ONCE and passed into every FT call.
        hash_started = perf_counter()
        identity = hf_identity(c)
        durable_json(root / "identity_hashing.json", {"seconds": perf_counter() - hash_started, "computed_once": True})
        durable_json(root / "hf_identity.json", identity)
        durable_json(root / "hf_file_pins.json", {
            path: {"bytes": Path(path).stat().st_size, "mtime_ns": Path(path).stat().st_mtime_ns}
            for path in identity["files"]})
        provider = OllamaProvider(model_name=direct.MODELS["qwen_base"][0])
        if provider.resolve_model_digest() != c.generation_model_digest:
            raise ValueError("Qwen identity mismatch")
        durable_json(root / "ollama_identity.json", provider.describe_model())
        manifests = Path(load_rag_config(c.retrieval_config).vector_store.persist_path) / "manifests"
        index = {str(p.resolve()): file_sha256(p) for p in sorted(manifests.glob("*.json"))}
        if not index:
            raise ValueError("No existing index manifests")
        durable_json(root / "index_identity.json", index)
        durable_json(root / "job_plan.json", plan)
        durable_json(root / "schema.json", TestingBodiesAnswer.model_json_schema())
        audit = read(root / "leakage_audit.json")
        for path, digest in audit["snapshots"].items():
            if file_sha256(Path(path)) != digest:
                raise ValueError("Audit snapshot changed: " + path)
        files = {root / n for n in ["selection.json", "leakage_audit.json", "job_plan.json",
                 "hf_identity.json", "hf_file_pins.json", "ollama_identity.json",
                 "index_identity.json", "schema.json", "identity_hashing.json"]}
        files.update(Path(path) for path in audit["snapshots"])
        files.add(Path("data/raw/methods2test/dataset/eval.tar.bz2"))
        files.add(Path("scripts/benchmarks/run_methods2test_hundred.py"))
        for published in ["data/validation/methods2test_unused_eval_hundred_v1/selection.jsonl", "configs/datasets/manifests/methods2test_unused_eval_hundred_v1.json"]:
            if Path(published).exists():
                files.add(Path(published))
        for item in audit["candidates"]:
            corpus = Path(item["corpus_path"])
            if file_sha256(corpus) != item["corpus_sha256"]:
                raise ValueError("Selected corpus changed")
            files.add(corpus)
        for ident in selected["ids"]:
            cr = root / "cases" / ident
            case = ExperimentCase.model_validate(read(cr / "case.json"))
            if case.case_id != ident:
                raise ValueError("Case identity mismatch: " + ident)
            gold = read(cr / "raw-private.json")["raw"]["test_case"]["body"]
            for arm in ARMS:
                out = cr / "frozen_prompts" / arm
                out.mkdir(parents=True, exist_ok=True)
                if arm == "ft_testing":
                    prompt = format_inference_prompt(ft_case(case).instruction, case.input_text)
                elif arm == "qwen_base":
                    prompt = profile.BodyPromptBuilder().build(task="testing", instruction=case.instruction,
                        input_text=case.input_text, requirements=case.requirements,
                        project_context=case.project_context, contexts=(), approach="direct").text
                else:
                    prompt = _render_rag(c, case, out, arm, audit)
                if prompt.count(profile.DEMO_BLOCK) != 1 or (gold and gold in prompt):
                    raise ValueError("One-shot/gold isolation failure: " + ident + "/" + arm)
                (out / "prompt.txt").write_text(prompt, encoding="utf-8")
                durable_json(out / "prompt_identity.json", {"sha256": sha(prompt), "before_model_calls": True})
            for name in ["case.json", "scaffold.java", "prepared.json", "raw-private.json", "reference-private.java"]:
                files.add(cr / name)
            files.update(cr.glob("*.java"))
            files.update(cr.glob("*original-private.json"))
            files.update(p for p in (cr / "frozen_prompts").rglob("*") if p.is_file())
            prepared = read(cr / "prepared.json")
            reference = read(cr / "reference-coverage/coverage.json")
            class_file = Path(prepared["revision"]["bin_classes"]) / (prepared["focal_class"].replace(".", "/") + ".class")
            if (reference["status"] != "passed" or not reference["focal_invoked"] or not reference["coverage"]
                    or file_sha256(cr / "reference-private.java") != prepared["reference_sha256"]
                    or sha(case.input_text) != prepared["production_sha256"]
                    or file_sha256(class_file) != reference["production_class_sha256"]):
                raise ValueError("Instrumented reference/source identity failed: " + ident)
            files.update(p for p in (cr / "reference-coverage").rglob("*") if p.is_file())
            files.add(cr / "source-review-before-execution.json")
            revision = prepared["revision"]
            files.update(Path(revision["bin_classes"]).rglob("*.class"))
            files.update(Path(p) for p in revision.get("dependencies", []))
        # Preserve the original pilot's evaluator/role configuration pins as well.
        for name in ["configs/evaluation/methods2test_assertions_v1.json",
                     "configs/evaluation/jacoco_v1.json",
                     "configs/datasets/manifests/methods2test_unused_eval_v1.json",
                     "data/validation/methods2test_unused_eval_v1/selection.jsonl"]:
            if Path(name).is_file():
                files.add(Path(name))
        for name in ["selection_protocol.json", "preparation_progress.json"]:
            if (root / name).is_file():
                files.add(root / name)
        files.update(p for p in (root / "demo").rglob("*") if p.is_file())
        files.update(p for p in (root / "controls").rglob("*") if p.is_file())
        sources = build_dependency_identity(c)
        for name in ["configs/benchmarks/defects4j_jupiter_v1.yaml",
                     "scripts/benchmarks/run_methods2test_hundred.py",
                     "scripts/benchmarks/census_methods2test_eval.py"]:
            if Path(name).is_file():
                sources[str(Path(name).resolve())] = file_sha256(Path(name))
        sources[str(CONFIG.resolve())] = file_sha256(CONFIG)
        for name in sources:
            source = Path(name)
            target = root / "source_snapshot" / source.relative_to(Path.cwd())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            files.add(target)
        durable_json(root / "freeze.json", {
            "protocol": PROTOCOL, "files": {str(p.absolute()): file_sha256(p) for p in sorted(files)},
            "sources": sources, "config": file_sha256(CONFIG), "created_at": now(),
            "created_before_model_calls": True, "frozen_prompt_count": MAX_CALLS,
            "hf_verification": "SHA256 at freeze, size/mtime pins on resume; cached identity, no per-cell weight hashing",
            "java": {str(p): file_sha256(p) for p in [c.java_home / "bin/java", c.java_home / "bin/javac", c.junit_jar]},
        }, exclusive=True)
        progress(root)


def verify(root):
    root = Path(root).resolve()
    selection(root)
    protocol()
    frozen = read(root / "freeze.json")
    if frozen.get("protocol") != PROTOCOL or frozen.get("frozen_prompt_count") != MAX_CALLS:
        raise ValueError("Not a complete hundred-case freeze")
    for key in ["files", "sources", "java"]:
        for path, digest in frozen[key].items():
            if file_sha256(Path(path)) != digest:
                raise ValueError("Frozen dependency changed: " + path)
    if file_sha256(CONFIG) != frozen["config"]:
        raise ValueError("Protocol changed")
    for path, digest in read(root / "index_identity.json").items():
        if file_sha256(Path(path)) != digest:
            raise ValueError("Index changed: " + path)
    for path, pin in read(root / "hf_file_pins.json").items():
        stat = Path(path).stat()
        if {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns} != pin:
            raise ValueError("Pinned local HF file changed: " + path)
    return frozen


def _generate_direct(c, case, out, ledger):
    tokens = direct.counter()
    provider = OllamaProvider(model_name=direct.MODELS["qwen_base"][0], temperature=0,
        top_p=.9, max_tokens=4096, context_window_tokens=32768, seed=42,
        timeout_seconds=1800, opener=ledger)
    if provider.resolve_model_digest() != c.generation_model_digest:
        raise ValueError("Pinned Qwen generation digest changed")
    runner = RagExperimentRunner(retriever=VectorRetriever(direct.ForbiddenStore()),
        llm_provider=provider, token_counter=tokens, total_context_tokens=32768,
        reserved_output_tokens=4096, runtime_context_tokens=32768,
        fail_on_prompt_budget_exceeded=True, structured_retries=0,
        prompt_builder=profile.BodyPromptBuilder(), structured_answer_model=TestingBodiesAnswer)
    exp = direct.experiment(out, "qwen_base", tokens).model_copy(update={
        "baseline_id": PROTOCOL, "dataset_version": case.metadata.get("dataset_version", "methods2test-unused-eval-hundred-v1")})
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
        if not isinstance(server, dict) or server.get("error") or not isinstance(server.get("response"), str):
            return True
    return not isinstance(raw, str) or not raw.strip()


def _recover(root):
    for path in _dispatches(root):
        if not (path.parent / "completion.json").exists() and not (path.parent / "interrupted.json").exists():
            durable_json(path.parent / "interrupted.json", {
                "status": "interrupted_unresolved", "recovered_at": now(),
                "retry_forbidden": True, "reason": "Charge exists without durable completion; request outcome unknown",
            }, exclusive=True)


def _gate(root, arm, ident, status):
    first = selection(root)["ids"][0]
    path = root / (arm + "-gate.json")
    if ident == first and not path.exists():
        durable_json(path, {"id": ident, "arm": arm, "status": status,
            "usable_transport": status not in {"infrastructure_failure", "pre_dispatch_failure", "interrupted_unresolved"},
            "compile_success_required": False, "checked_at": now()}, exclusive=True)


def generate(root, arm, *, first_cell_callback=None):
    """Resume uncharged cells sequentially; no cross-arm compilation gate/retries."""
    root = Path(root).resolve()
    if arm not in ARMS:
        raise ValueError("Explicit planned arm required")
    with file_lock(root, ".run.lock", blocking=False):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        verify(root)
        _recover(root)
        ids = selection(root)["ids"]
        for ident in ids:
            if (output_dir(root, ident, arm) / "interrupted.json").exists():
                _gate(root, arm, ident, "interrupted_unresolved")
        progress(root, active_arm=arm, running=True)
        loaded = None
        try:
            if (root / (arm + "-stop.json")).exists():
                return progress(root)
            pending = [ident for ident in ids if not any(
                (output_dir(root, ident, arm) / name).exists() for name in ["dispatch.json", "completion.json"])]
            if not pending:
                return progress(root)
            c = runtime()
            identity = read(root / "hf_identity.json")
            if arm == "ft_testing":
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                started = perf_counter()
                try:
                    loaded = load_eval_model(identity["model"], {**identity["inference"],
                        "local_files_only": True, "trust_remote_code": False})
                except Exception as exc:
                    durable_json(root / (arm + "-stop.json"), {"id": pending[0],
                        "status": "pre_dispatch_failure", "reason": "Local FT load failed: " + str(exc),
                        "created_at": now()}, exclusive=True)
                    _gate(root, arm, pending[0], "pre_dispatch_failure")
                    raise
                durable_json(root / ("ft_load-" + uuid4().hex + ".json"), {
                    "seconds": perf_counter() - started, "loaded_once_for_batch": True,
                    "planned_cells": len(pending), "created_at": now()})
            for ident in pending:
                out = output_dir(root, ident, arm)
                out.mkdir(parents=True, exist_ok=True)
                case = ExperimentCase.model_validate(read(root / "cases" / ident / "case.json"))
                ledger, started = Ledger(root, ident, arm), perf_counter()
                raw, generated = "", None
                try:
                    if arm == "ft_testing":
                        generated = generate_ft(c, ft_case(case), out, loaded_model=loaded,
                            model_identity=identity, before_generation=lambda prompt: ledger.charge({
                                "prompt": prompt, "max_new_tokens": 4096, "do_sample": False,
                                "seed": 42, "top_p": .9, "context_window_tokens": 32768}))
                    elif arm == "qwen_base":
                        generated = _generate_direct(c, case, out, ledger)
                    else:
                        generated = generate_rag(c, case, out, arm, read(root / "leakage_audit.json"),
                                                 body_profile=True, opener=ledger)
                    if ledger.dispatch_time is None:
                        raise RuntimeError("Generator returned without charged dispatch")
                    raw = _raw(out, generated)
                    (out / "raw.txt").write_text(raw, encoding="utf-8")
                    durable_json(out / "received.json", generated)
                    if _infrastructure(out, raw):
                        raise RuntimeError("Empty response or API infrastructure anomaly")
                    answer = parse_testing_bodies(raw)
                    durable_json(out / "bodies.json", answer.model_dump())
                    source = assemble((root / "cases" / ident / "scaffold.java").read_text(encoding="utf-8"), answer)
                    (out / "generated.java").write_text(source, encoding="utf-8")
                    durable_json(out / "generation.json", {**generated,
                        "source_sha256": sha(source), "assembled": True})
                    status = "assembled"
                except Exception as exc:
                    raw = _raw(out, generated, exc)
                    if raw:
                        (out / "raw.txt").write_text(raw, encoding="utf-8")
                    durable_json(out / "failure.json", generation_failure_payload(exc,
                        case_sha256=file_sha256(root / "cases" / ident / "case.json"), arm=arm))
                    charged = (out / "dispatch.json").exists()
                    status = ("pre_dispatch_failure" if not charged else
                              "infrastructure_failure" if (_infrastructure(out, raw)
                                  or isinstance(exc, InfrastructureFailure)
                                  or (isinstance(exc, StructuredOutputError) and not exc.attempts))
                              else "model_output_failure")
                if status in {"infrastructure_failure", "pre_dispatch_failure"}:
                    # Persist fail-stop BEFORE completion: a crash must not reopen this arm.
                    durable_json(root / (arm + "-stop.json"), {"id": ident, "status": status,
                        "reason": "Transport, empty response, or API/pre-dispatch infrastructure anomaly",
                        "created_at": now()}, exclusive=True)
                durable_json(out / "completion.json", {"assembled": status == "assembled",
                    "status": status, "generation_pipeline_seconds": perf_counter() - started,
                    "dispatch_to_return_seconds": (perf_counter() - ledger.dispatch_time
                        if ledger.dispatch_time is not None else None), "completed_at": now()}, exclusive=True)
                _gate(root, arm, ident, status)
                if ident == ids[0] and first_cell_callback is not None:
                    first_cell_callback(root)
                progress(root, active_arm=arm, running=True)
                print(status.upper(), arm, ident, flush=True)
                if status in {"infrastructure_failure", "pre_dispatch_failure"}:
                    break
        finally:
            if loaded is not None:
                del loaded
                import gc
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            progress(root)
        return read(root / "progress.json")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["freeze", "verify", "generate"])
    p.add_argument("--run-id", required=True)
    p.add_argument("--arm", choices=ARMS)
    args = p.parse_args(argv)
    require_wsl()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
    validate_evaluation_run_id(args.run_id)
    root = (Path("artifacts/evaluation/runs") / args.run_id).resolve()
    if args.action == "freeze":
        freeze(root)
    elif args.action == "verify":
        verify(root)
    else:
        if args.arm is None:
            p.error("generate requires --arm")
        generate(root, args.arm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
