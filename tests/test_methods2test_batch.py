"""Model-free tests only: fake generation/provider boundaries, never GPU/index work."""
from io import BytesIO
import json
import multiprocessing
import sys
from types import SimpleNamespace
from urllib.request import Request

import pytest

from llm_ontology.benchmarks import methods2test_batch as batch
from llm_ontology.inference.structured_output import StructuredOutputError


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir()
    ids = [f"123_{i}" for i in range(100)]
    batch.durable_json(root / "selection.json", {"ids": ids, "cases": [{"id": i} for i in ids]})
    batch.durable_json(root / "leakage_audit.json", {"checked": True, "snapshots": {}, "candidates": []})
    batch.durable_json(root / "hf_identity.json", {"model": {"model_path": "local-base", "adapter_path": "b2"},
                                                  "inference": {}, "files": {}})
    for ident in ids:
        cr = root / "cases" / ident
        batch.durable_json(cr / "case.json", {"case_id": ident, "instruction": "test this",
            "input_text": "public class Util {}", "metadata": {"protocol": batch.PROTOCOL}})
        (cr / "scaffold.java").write_text("scaffold")
        for arm in batch.ARMS:
            p = cr / "frozen_prompts" / arm / "prompt.txt"
            p.parent.mkdir(parents=True)
            p.write_text("frozen " + ident + "/" + arm)
    monkeypatch.setattr(batch, "verify", lambda root: {})
    monkeypatch.setattr(batch, "runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(batch, "parse_testing_bodies", lambda raw: SimpleNamespace(model_dump=lambda: json.loads(raw)))
    monkeypatch.setattr(batch, "assemble", lambda scaffold, answer: "class GeneratedBodyTests {}")
    monkeypatch.setattr(batch, "ft_case", lambda case: case)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    return root, ids


def payload(root, ident, arm):
    return {"prompt": (root / "cases" / ident / "frozen_prompts" / arm / "prompt.txt").read_text()}


def fake_generator(root, calls, failure=None):
    def dispatch(case, out, ledger):
        ident = case.case_id
        ledger.charge(payload(root, ident, ledger.arm))
        calls.append((ident, ledger.arm))
        raw = json.dumps({"testCase1": "assertTrue(true);", "testCase2": "assertTrue(true);"})
        if failure == "empty" or (failure == "first_empty" and len(calls) == 1):
            raw = "   "
        elif failure == "syntax":
            raw = "nonempty invalid JSON or Java"
        (out / "raw.txt").write_text(raw)
        if failure == "transport":
            (out / "raw.txt").unlink()
            raise RuntimeError("offline transport")
        if failure == "syntax":
            raise ValueError("ordinary model output syntax")
        return {"source": raw}
    return dispatch


def test_exactly_hundred_matching_ids_and_cases(prepared):
    root, ids = prepared
    assert batch.selection(root)["ids"] == ids
    selected = batch.read(root / "selection.json")
    selected["cases"][1]["id"] = ids[0]
    batch.durable_json(root / "selection.json", selected)
    with pytest.raises(ValueError, match="matching ordered"):
        batch.selection(root)


@pytest.mark.parametrize("change", ["duplicate", "short", "unsafe"])
def test_invalid_selection(prepared, change):
    root, ids = prepared
    if change == "duplicate":
        ids[1] = ids[0]
    elif change == "short":
        ids.pop()
    else:
        ids[1] = "../escape"
    batch.durable_json(root / "selection.json", {"ids": ids, "cases": [{"id": i} for i in ids]})
    with pytest.raises(ValueError):
        batch.selection(root)


def test_all_four_hundred_charges_are_exclusive(prepared, monkeypatch):
    root, ids = prepared
    # Ledger-cap test does not need the O(matrix) derived progress after every charge.
    monkeypatch.setattr(batch, "_progress", lambda *args, **kwargs: None)
    for ident in ids:
        for arm in batch.ARMS:
            ledger = batch.Ledger(root, ident, arm)
            ledger.charge(payload(root, ident, arm))
            with pytest.raises(FileExistsError):
                ledger.charge(payload(root, ident, arm))
    assert len(batch._dispatches(root)) == 400
    assert all(batch.read(p)["charged_to_budget"] for p in batch._dispatches(root))
    with pytest.raises(ValueError, match="Unplanned"):
        batch.Ledger(root, "unknown", batch.ARMS[0])


def _race_charge(root, ident, barrier, queue):
    barrier.wait(timeout=5)
    try:
        batch.Ledger(root, ident, "qwen_base").charge(payload(root, ident, "qwen_base"))
        queue.put("charged")
    except (RuntimeError, FileExistsError):
        queue.put("rejected")


@pytest.mark.parametrize("same_cell", [False, True])
def test_flock_atomic_budget_and_same_cell_races(prepared, monkeypatch, same_cell):
    root, ids = prepared
    monkeypatch.setattr(batch, "MAX_CALLS", 1)
    monkeypatch.setattr(batch, "_progress", lambda *args, **kwargs: None)
    ctx = multiprocessing.get_context("fork")
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_race_charge, args=(root, ids[0 if same_cell else i], barrier, queue))
               for i in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert not worker.is_alive()
        assert worker.exitcode == 0
    assert sorted(queue.get(timeout=1) for _ in workers) == ["charged", "rejected"]
    assert len(batch._dispatches(root)) == 1


def test_prompt_drift_is_rejected_before_charge(prepared):
    root, ids = prepared
    ledger = batch.Ledger(root, ids[0], "qwen_base")
    with pytest.raises(ValueError, match="differs"):
        ledger.charge({"prompt": "not frozen"})
    assert not (ledger.out / "dispatch.json").exists()


@pytest.mark.parametrize("arm", batch.ARMS)
def test_sequential_hundred_each_arm_and_idempotent_resume(prepared, monkeypatch, arm):
    root, ids = prepared
    calls, loads, identities = [], [], []
    dispatch = fake_generator(root, calls)
    monkeypatch.setattr(batch, "_generate_direct", lambda c, case, out, ledger: dispatch(case, out, ledger))
    monkeypatch.setattr(batch, "generate_rag", lambda c, case, out, arm, audit, **kw: dispatch(case, out, kw["opener"]))
    monkeypatch.setattr(batch, "load_eval_model", lambda model, inference: loads.append(inference) or (object(), object()))
    def fake_ft(c, case, out, **kw):
        assert kw["loaded_model"] is not None
        identities.append(kw["model_identity"])
        kw["before_generation"](payload(root, case.case_id, arm)["prompt"])
        calls.append((case.case_id, arm))
        (out / "raw.txt").write_text('{"testCase1":"x();", "testCase2":"x();"}')
        return {"generation": {"tokens": 6}}
    monkeypatch.setattr(batch, "generate_ft", fake_ft)
    monkeypatch.setattr(batch, "hf_identity", lambda *a, **k: pytest.fail("identity recomputed during batch"))
    result = batch.generate(root, arm)
    assert calls == [(ident, arm) for ident in ids]
    assert result["counts"]["charged"] == result["counts"]["assembled"] == 100
    assert result["remaining_budget"] == 300
    assert not result["running"]
    assert batch.read(root / (arm + "-gate.json"))["compile_success_required"] is False
    batch.generate(root, arm)
    assert len(calls) == 100
    if arm == "ft_testing":
        assert len(loads) == 1
        assert loads[0]["local_files_only"] and not loads[0]["trust_remote_code"]
        assert len({id(identity) for identity in identities}) == 1
    else:
        assert not loads


def test_ordinary_first_syntax_failure_does_not_gate_rest(prepared, monkeypatch):
    root, _ = prepared
    calls = []
    dispatch = fake_generator(root, calls, "syntax")
    monkeypatch.setattr(batch, "_generate_direct", lambda c, case, out, ledger: dispatch(case, out, ledger))
    gate_calls = []
    result = batch.generate(root, "qwen_base", first_cell_callback=lambda root: gate_calls.append(len(calls)))
    assert gate_calls == [1]
    assert len(calls) == 100
    assert result["counts"]["model_output_failure"] == 100
    assert batch.read(root / "qwen_base-gate.json")["usable_transport"]
    assert not (root / "qwen_base-stop.json").exists()


@pytest.mark.parametrize("arm", batch.ARMS)
@pytest.mark.parametrize("failure", ["empty", "transport"])
def test_each_arm_fail_stops_on_first_infrastructure_anomaly(prepared, monkeypatch, arm, failure):
    root, _ = prepared
    calls = []
    dispatch = fake_generator(root, calls, failure)
    monkeypatch.setattr(batch, "_generate_direct", lambda c, case, out, ledger: dispatch(case, out, ledger))
    monkeypatch.setattr(batch, "generate_rag", lambda c, case, out, arm, audit, **kw: dispatch(case, out, kw["opener"]))
    monkeypatch.setattr(batch, "load_eval_model", lambda *a: (object(), object()))
    def fake_ft(c, case, out, **kw):
        kw["before_generation"](payload(root, case.case_id, arm)["prompt"])
        calls.append((case.case_id, arm))
        (out / "raw.txt").write_text("" if failure == "empty" else "")
        if failure == "transport":
            raise RuntimeError("CUDA/API infrastructure failed")
        return {}
    monkeypatch.setattr(batch, "generate_ft", fake_ft)
    result = batch.generate(root, arm)
    assert len(calls) == 1
    assert result["counts"]["charged"] == result["counts"]["infrastructure_failure"] == 1
    assert result["counts"]["blocked"] == 99
    assert not batch.read(root / (arm + "-gate.json"))["usable_transport"]
    batch.generate(root, arm)
    assert len(calls) == 1


def test_interrupted_charge_is_unresolved_and_others_continue(prepared, monkeypatch):
    root, ids = prepared
    ledger = batch.Ledger(root, ids[0], "qwen_base")
    ledger.charge(payload(root, ids[0], "qwen_base"))
    calls = []
    dispatch = fake_generator(root, calls)
    monkeypatch.setattr(batch, "_generate_direct", lambda c, case, out, ledger: dispatch(case, out, ledger))
    result = batch.generate(root, "qwen_base")
    assert calls == [(ident, "qwen_base") for ident in ids[1:]]
    assert result["counts"]["charged"] == 100
    assert result["counts"]["assembled"] == 99
    assert result["counts"]["interrupted_unresolved"] == 1
    assert not (ledger.out / "completion.json").exists()
    assert batch.read(ledger.out / "interrupted.json")["retry_forbidden"]
    batch.generate(root, "qwen_base")
    assert len(calls) == 99
    assert batch.read(root / "dispatch_ledger.json")["charged"] == 100


def test_run_lock_prevents_parallel_generators(prepared):
    root, _ = prepared
    with batch.file_lock(root, ".run.lock", blocking=False):
        with pytest.raises(RuntimeError, match="owned"):
            batch.generate(root, "qwen_base")


def test_progress_starttime_persists_and_counts_unresolved(prepared):
    root, ids = prepared
    first = batch.progress(root)
    batch.Ledger(root, ids[0], "qwen_base").charge(payload(root, ids[0], "qwen_base"))
    second = batch.progress(root)
    assert second["started_at"] == first["started_at"]
    assert second["remaining_budget"] == second["remaining"] == 399
    assert second["counts"]["interrupted_unresolved"] == 1
    assert len(second["cells"]) == 400


def test_transport_preserves_raw_and_failed_call_consumes_budget(prepared, monkeypatch):
    root, ids = prepared
    ledger = batch.Ledger(root, ids[0], "qwen_base")
    request_payload = {**payload(root, ids[0], "qwen_base"), "model": "qwen2.5-coder:7b",
                       "stream": False, "options": batch.OPTIONS,
                       "format": batch.TestingBodiesAnswer.model_json_schema()}
    seen = []
    def opener(request, **kw):
        seen.append(json.loads(request.data))
        return BytesIO(b'{"response":"nonempty invalid syntax", "done":true}')
    monkeypatch.setattr(batch, "urlopen", opener)
    request = Request("http://localhost:11434/api/generate", data=json.dumps(request_payload).encode())
    assert json.loads(ledger(request).read())["response"] == "nonempty invalid syntax"
    assert seen[0]["keep_alive"] == 0
    assert ledger.out.joinpath("server_response.json").exists()
    assert not batch._infrastructure(ledger.out, "nonempty invalid syntax")
    with pytest.raises(FileExistsError):
        ledger(request)
    assert len(seen) == 1


def test_preview_never_forwards_generation_and_keeps_runner_trace(tmp_path, monkeypatch):
    out = tmp_path / "preview"
    out.mkdir()
    calls = []
    monkeypatch.setattr(batch, "urlopen", lambda request, **kw: calls.append(request.full_url) or BytesIO(b'{}'))
    def fake_rag(c, case, output, arm, audit, **kw):
        req = {"model": "qwen2.5-coder:7b", "stream": False, "prompt": "actual evidence",
               "options": batch.OPTIONS, "format": batch.TestingBodiesAnswer.model_json_schema()}
        try:
            kw["opener"](Request("http://localhost:11434/api/generate", data=json.dumps(req).encode()))
        except Exception as original:
            exc = StructuredOutputError(str(original), attempts=[])
            exc.failure_metadata["retrieval_trace"] = {"prompt_document_ids": ["frozen-doc"]}
            raise exc from original
    monkeypatch.setattr(batch, "generate_rag", fake_rag)
    assert batch._render_rag(None, None, out, "rag_single", {}) == "actual evidence"
    assert calls == []
    trace = batch.read(out / "preview_trace.json")
    assert trace["generation_calls"] == 0
    assert trace["failure_metadata"]["retrieval_trace"]["prompt_document_ids"] == ["frozen-doc"]


@pytest.mark.parametrize("server", [b'not JSON', b'[]', b'{"error":"OOM"}', b'{"response":42}'])
def test_api_envelope_anomaly_is_infrastructure(prepared, server):
    root, ids = prepared
    out = batch.output_dir(root, ids[0], "qwen_base")
    out.mkdir(parents=True)
    (out / "server_response.json").write_bytes(server)
    assert batch._infrastructure(out, "apparently nonempty")


def test_ft_loader_failure_does_not_spend_budget_and_stops_arm(prepared, monkeypatch):
    root, _ = prepared
    def fail(*args):
        raise RuntimeError("local model absent")
    monkeypatch.setattr(batch, "load_eval_model", fail)
    with pytest.raises(RuntimeError, match="absent"):
        batch.generate(root, "ft_testing")
    result = batch.read(root / "progress.json")
    assert result["counts"]["charged"] == 0
    assert result["counts"]["blocked"] == 100
    assert (root / "ft_testing-stop.json").exists()
    assert not result["running"]


def test_freeze_and_verify_all_prompts_sources_and_dependencies(tmp_path, monkeypatch):
    """Exercise full freeze wiring, substituting only expensive JVM/provider work."""
    # Keep actual selection/verify/freeze, unlike dispatch-only fixtures.
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "run"
    root.mkdir()
    config = tmp_path / "protocol.json"
    monkeypatch.setattr(batch, "CONFIG", config)
    plan = {"protocol": batch.PROTOCOL, "cases": 100, "max_actual_generation_calls": 400,
            "attempts_per_cell": 1, "retries": 0, "repairs": 0, "max_new_tokens": 4096,
            "seed": 42, "temperature": 0, "top_p": .9, "context_window_tokens": 32768,
            "prompt_profile": "testing-bodies-one-shot-v2", "indexing_allowed": False,
            "official_split": "eval", "arms": list(batch.ARMS)}
    batch.durable_json(config, plan)
    ids = [str(i) for i in range(100)]
    batch.durable_json(root / "selection.json", {"ids": ids, "cases": [{"id": i} for i in ids]})
    batch.durable_json(root / "leakage_audit.json", {"checked": True, "snapshots": {}, "candidates": []})
    source = tmp_path / "module.py"
    source.write_text("# frozen batch source")
    java = tmp_path / "jdk" / "bin"
    java.mkdir(parents=True)
    for name in ["java", "javac"]:
        (java / name).write_text("fake executable")
    jar = tmp_path / "junit.jar"
    jar.write_bytes(b"pinned")
    manifests = tmp_path / "index" / "manifests"
    manifests.mkdir(parents=True)
    batch.durable_json(manifests / "mixed.json", {"identity": "frozen"})
    c = SimpleNamespace(java_home=java.parent, junit_jar=jar,
                        generation_model_digest="digest", retrieval_config="rag.yaml")
    monkeypatch.setattr(batch, "runtime", lambda: c)
    monkeypatch.setattr(batch, "_controls", lambda *a: None)
    monkeypatch.setattr(batch, "hf_identity", lambda c: {"model": {}, "inference": {}, "files": {}})
    monkeypatch.setattr(batch, "load_rag_config", lambda *a: SimpleNamespace(vector_store=SimpleNamespace(persist_path=manifests.parent)))
    monkeypatch.setattr(batch, "build_dependency_identity", lambda c: {str(source): batch.file_sha256(source)})
    monkeypatch.setattr(batch, "OllamaProvider", lambda **kw: SimpleNamespace(
        resolve_model_digest=lambda: "digest", describe_model=lambda: {"digest": "digest"}))
    rendered = []
    def rag(c, case, out, arm, audit):
        rendered.append((case.case_id, arm))
        return batch.profile.DEMO_BLOCK + " actual evidence " + arm
    monkeypatch.setattr(batch, "_render_rag", rag)
    for ident in ids:
        cr = root / "cases" / ident
        case = batch.ExperimentCase(case_id=ident, instruction="test", input_text="package example; class Util {}",
                                    structured_identity={"class_name": "example.Util"})
        case = batch.profile.apply_profile(case)
        batch.durable_json(cr / "case.json", case.model_dump(mode="json"))
        batch.durable_json(cr / "raw-private.json", {"raw": {"test_case": {"body": "PRIVATE GOLD BODY"}}})
        for name in ["scaffold.java", "reference-private.java", "Util.java"]:
            (cr / name).write_text("frozen production or scaffold")
        classes = cr / "classes"
        classes.mkdir()
        (classes / "example").mkdir()
        (classes / "example/Util.class").write_bytes(b"bytecode")
        batch.durable_json(cr / "source-review-before-execution.json", {"reviewed": True})
        batch.durable_json(cr / "reference-coverage/coverage.json", {"status": "passed", "focal_invoked": True, "coverage": {"measured": True}, "production_class_sha256": batch.file_sha256(classes / "example/Util.class")})
        batch.durable_json(cr / "prepared.json", {"revision": {"bin_classes": str(classes), "dependencies": []}, "focal_class": "example.Util", "reference_sha256": batch.file_sha256(cr / "reference-private.java"), "production_sha256": batch.sha(case.input_text)})
    for pin in ["data/raw/methods2test/dataset/eval.tar.bz2", "scripts/benchmarks/run_methods2test_hundred.py"]:
        target = tmp_path / pin
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture pin")
    batch.freeze(root)
    frozen = batch.verify(root)
    assert len(rendered) == 200
    assert frozen["frozen_prompt_count"] == 400
    assert len(list(root.glob("cases/*/frozen_prompts/*/prompt.txt"))) == 400
    assert not list(root.glob("cases/*/predictions/*/dispatch.json"))
    assert (root / "source_snapshot/module.py").read_bytes() == source.read_bytes()
    with pytest.raises(FileExistsError):
        batch.freeze(root)
    prompt = root / "cases/0/frozen_prompts/rag_single/prompt.txt"
    prompt.write_text("tampered actual evidence")
    with pytest.raises(ValueError, match="Frozen dependency changed"):
        batch.verify(root)



def test_nonempty_api_contract_failure_stops_arm(prepared, monkeypatch):
    root, ids = prepared
    def fail(c, case, out, ledger):
        ledger.charge(payload(root, case.case_id, "qwen_base"))
        (out / "raw.txt").write_text("nonempty output but malformed runtime metadata")
        raise StructuredOutputError("invalid provider envelope", attempts=[])
    monkeypatch.setattr(batch, "_generate_direct", fail)
    result = batch.generate(root, "qwen_base")
    assert result["counts"]["infrastructure_failure"] == 1
    assert result["counts"]["charged"] == 1
    assert not batch.read(root / "qwen_base-gate.json")["usable_transport"]


def test_direct_digest_change_rejected_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(batch.direct, "counter", lambda: object())
    monkeypatch.setattr(batch, "OllamaProvider", lambda **kw: SimpleNamespace(resolve_model_digest=lambda: "changed"))
    with pytest.raises(ValueError, match="digest changed"):
        batch._generate_direct(SimpleNamespace(generation_model_digest="pinned"), None, tmp_path, None)


def test_live_protocol_matches_declared_finite_decoding():
    plan = batch.protocol()
    assert plan["max_actual_generation_calls"] == 400
    assert plan["top_p"] == .9 and plan["context_window_tokens"] == 32768
    assert plan["temperature"] == 0 and plan["seed"] == 42
