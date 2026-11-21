"""Matrix contract tests: no real model, network, GPU or production index writes."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_ontology.benchmarks import testing_matrix as matrix
from llm_ontology.benchmarks import methods2test_execution as offline
from llm_ontology.benchmarks.methods2test_statistics import aggregate


SOURCE = "public class Number {\n  public static int f(int n) {\n    if (n < 0) throw new IllegalArgumentException();\n    return n + 1;\n  }\n}\n"

try:
    from llm_ontology import ontology
    import rdflib  # noqa: F401
    import tree_sitter_java  # noqa: F401
    HAS_ONTOLOGY = True
except ImportError:
    HAS_ONTOLOGY = False
needs_ontology = pytest.mark.skipif(not HAS_ONTOLOGY, reason="rdflib/tree-sitter-java absent")


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.chdir(matrix.REPO)
    root = tmp_path / "run"
    matrix.write(root / "matrix_plan.json", matrix.load_plan(2))
    matrix.write(root / "selection.json", {"ids": ["one", "two"],
        "cases": [{"id": "one"}, {"id": "two"}],
        "indexing_allowed": False, "split": "official eval"})
    matrix.write(root / "context/identity.json", {"sha256": "skill"})
    (root / "context/SKILL.md").write_text("Existing testing process guidance.")
    matrix.write(root / "leakage_audit.json", {})
    for ident in ["one", "two"]:
        case = root / "cases" / ident
        matrix.write(case / "case.json", {"case_id": ident, "instruction": "Generate tests",
            "input_text": SOURCE, "requirements": "Return JSON bodies only.", "project_context": "API context",
            "structured_identity": {"class_name": "org.x.Number", "method_name": "f"}})
        (case / "scaffold.java").write_text("scaffold")
        if HAS_ONTOLOGY:
            matrix.batch.freeze_ontology(case / "ontology", lambda: ontology.testing_context(
                matrix.ExperimentCase.model_validate(matrix.read(case / "case.json"))), "project-ontology-v1")
        for arm in matrix.ARMS:
            prompt = case / "frozen_prompts" / arm / "prompt.txt"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("frozen " + ident + "/" + arm)
    monkeypatch.setattr(matrix.batch, "runtime", lambda: SimpleNamespace())
    return matrix.Matrix(root)


def fake_direct(c, case, out, ledger, **kwargs):
    ledger.charge({"prompt": (ledger.root / "cases" / case.case_id /
        "frozen_prompts" / ledger.arm / "prompt.txt").read_text()})
    (out / "raw.txt").write_text('{"testCase1":"assertTrue(true);","testCase2":"assertTrue(true);"}')
    return {}


def test_plan_and_skill_are_existing_inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(matrix.REPO)
    default = matrix.load_plan()
    assert default["cases"] == 100 and default["max_actual_generation_calls"] == 800
    plan = matrix.load_plan(7)
    assert plan["max_actual_generation_calls"] == 56
    assert plan["arms"] == list(matrix.ARMS)
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"# Workflow\r\nExisting process\r\n")
    resolved, content = matrix.resolve_skill(path)
    assert resolved == path and content.encode() == path.read_bytes()
    with pytest.raises(ValueError):
        matrix.load_plan(0)


def test_skill_variant_changes_only_instruction(prepared):
    base, skills = prepared.case("one", "qwen_base"), prepared.case("one", "skills")
    assert base.model_dump(exclude={"instruction"}) == skills.model_dump(exclude={"instruction"})
    assert skills.instruction.startswith(base.instruction)
    assert "Existing testing process guidance." in skills.instruction
    assert "Existing testing process guidance." not in matrix.direct_prompt(base)
    assert "Existing testing process guidance." in matrix.direct_prompt(skills)


@pytest.mark.parametrize("bad", ["../escape", ".", "x/y", "x\\y"])
def test_unsafe_or_incomplete_cohort_rejected(prepared, bad):
    selection = matrix.read(prepared.root / "selection.json")
    selection["ids"][0] = bad
    matrix.write(prepared.root / "selection.json", selection)
    with pytest.raises(ValueError):
        matrix.Matrix(prepared.root)


def test_ledger_prompt_identity_and_exclusive_charges(prepared):
    ledger = matrix.Ledger(prepared, "one", "skills")
    with pytest.raises(ValueError, match="frozen"):
        ledger.charge({"prompt": "modified"})
    ledger.charge({"prompt": "frozen one/skills"})
    with pytest.raises(FileExistsError):
        ledger.charge({"prompt": "frozen one/skills"})
    assert len(prepared.dispatches()) == 1
    assert ledger.dispatch_time is not None


def test_successful_and_failed_cells_are_not_retried(prepared, monkeypatch):
    monkeypatch.setattr(matrix.batch, "_generate_direct", fake_direct)
    monkeypatch.setattr(matrix.batch, "assemble", lambda *a: "class GeneratedBodyTests {}")
    prepared.generate("skills")
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 2
    assert all(matrix.read(prepared.out(i, "skills") / "completion.json")["status"] == "assembled"
               for i in prepared.ids)


def test_empty_transport_fail_stops_only_affected_arm(prepared, monkeypatch):
    def empty(c, case, out, ledger, **kwargs):
        fake_direct(c, case, out, ledger)
        (out / "raw.txt").write_text("")
        raise RuntimeError("empty response")
    monkeypatch.setattr(matrix.batch, "_generate_direct", empty)
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 1
    assert (prepared.root / "skills-stop.json").exists()
    assert not (prepared.root / "qwen_base-stop.json").exists()
    assert not (prepared.out("two", "skills") / "dispatch.json").exists()


def test_interrupted_charged_cell_is_never_retried(prepared, monkeypatch):
    matrix.Ledger(prepared, "one", "skills").charge({"prompt": "frozen one/skills"})
    monkeypatch.setattr(matrix.batch, "_generate_direct", lambda *a, **kw: pytest.fail("retry"))
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 1
    assert prepared.progress()["cells"]["one/skills"] == "interrupted_unresolved"


def test_invalid_output_counts_as_failed_attempt_not_arm_stop(prepared, monkeypatch):
    def invalid(c, case, out, ledger, **kwargs):
        fake_direct(c, case, out, ledger)
        (out / "raw.txt").write_text("not JSON")
        raise ValueError("invalid JSON")
    monkeypatch.setattr(matrix.batch, "_generate_direct", invalid)
    prepared.generate("skills")
    report = aggregate(prepared.root, arms=matrix.ARMS)
    assert report["arms"]["skills"]["class_pass"]["denominator"] == 2
    assert report["arms"]["skills"]["class_pass"]["count"] == 0
    assert report["arms"]["qwen_base"]["unattempted_cases"] == 2
    assert len(report["paired_comparisons"]) == 28
    primary = aggregate(prepared.root, arms=matrix.ARMS, pairs=prepared.plan["primary_pairs"])
    assert [(c["arm_a"], c["arm_b"]) for c in primary["paired_comparisons"]] == \
        [tuple(p) for p in prepared.plan["primary_pairs"]]
    assert not (prepared.root / "skills-stop.json").exists()


def test_new_skill_arm_is_reviewed_before_execution(prepared, monkeypatch):
    out = prepared.out("one", "skills")
    matrix.write(out / "generation.json", {"source_sha256": matrix.batch.sha("class T {void t(){System.exit(0);}}")})
    (out / "generated.java").write_text("class T {void t(){System.exit(0);}}")
    assert offline.review(prepared.root, arms=matrix.ARMS) == {}
    assert matrix.read(out / "metrics.json")["statuses"] == ["source_review_rejected"]


def test_dry_run_has_no_files_or_model_calls(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(matrix.REPO)
    monkeypatch.setattr(matrix, "REPO", tmp_path)
    monkeypatch.setattr(matrix, "CONFIG", Path(__file__).resolve().parents[1] / matrix.CONFIG)
    skill = tmp_path / "SKILL.md"
    skill.write_text("process guidance")
    assert matrix.main(["--run-id", "plan-only", "--cases", "1", "--skill-file", str(skill), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["max_actual_generation_calls"] == 8
    assert not (tmp_path / "artifacts").exists()


def test_plan_maps_every_ft_arm_to_one_adapter(monkeypatch):
    monkeypatch.chdir(matrix.REPO)
    plan = matrix.load_plan()
    assert "rag_multi" not in plan["arms"]
    assert plan["adapters"] == {"ft_testing": "b2_testing_v3", "ft_v3_onto": "b2_testing_v3",
                                "ft_onto": "b2_testing_onto"}
    broken = {**plan, "adapters": {"ft_testing": "b2_testing_v3"}}
    with pytest.raises(ValueError, match="adapter"):
        matrix.batch.check_arm_plan(broken, matrix.ARMS, matrix.FT_ARMS)
    with pytest.raises(ValueError, match="pairs"):
        matrix.batch.check_arm_plan({**plan, "primary_pairs": [["ft_onto", "rag_multi"]]},
                                    matrix.ARMS, matrix.FT_ARMS)


@needs_ontology
def test_each_ontology_arm_adds_only_the_frozen_block(prepared):
    block = (prepared.root / "cases/one/ontology/block.txt").read_text()
    assert block.startswith("<project-ontology>") and "throw IllegalArgumentException" in block
    pairs = {"onto_project": "qwen_base", "skills_onto": "skills", "ft_v3_onto": "ft_testing",
             "ft_onto": "ft_testing"}
    for onto_arm, control in pairs.items():
        with_block, without = prepared.case("one", onto_arm), prepared.case("one", control)
        assert with_block.model_dump(exclude={"instruction"}) == without.model_dump(exclude={"instruction"})
        assert with_block.instruction == matrix.batch.with_ontology(without.instruction, block)
        assert block not in prepared.prompt("one", control)
    # The two FT ontology arms see the same prompt; only the adapter differs.
    assert prepared.prompt("one", "ft_v3_onto") == prepared.prompt("one", "ft_onto")
    # Same rendering as the v3_onto training records: instruction + block, then the input.
    base = matrix.batch.ft_case(prepared.case("one", "qwen_base"))
    assert prepared.prompt("one", "ft_onto") == matrix.format_inference_prompt(
        matrix.batch.with_ontology(base.instruction, block), base.input_text)


@needs_ontology
def test_changed_frozen_block_is_rejected(prepared):
    path = prepared.root / "cases/one/ontology/block.txt"
    path.write_text(path.read_text() + "\nextra")
    with pytest.raises(ValueError, match="block changed"):
        prepared.case("one", "onto_project")
    assert prepared.case("one", "qwen_base")  # arms without the block do not read it


def _fake_adapter(root, name):
    adapter = root / "adapters" / name
    adapter.mkdir(parents=True)
    files = {}
    for file in ["adapter_config.json", "adapter_model.safetensors"]:
        (adapter / file).write_text(name + " " + file)
        files[str(adapter / file)] = {"bytes": (adapter / file).stat().st_size,
                                      "sha256": matrix.batch.file_sha256(adapter / file)}
    matrix.write(root / "hf_identity" / (name + ".json"),
                 {"model": {"name": name, "adapter_path": str(adapter)}, "inference": {}, "files": files,
                  "prompt_contract": "instruction-v1"})
    return adapter


@needs_ontology
def test_ft_arm_loads_its_own_verified_adapter_and_sends_the_frozen_prompt(prepared, monkeypatch):
    """Acceptance: adapter hash at load time and byte-identical prompt at the model call."""
    import sys
    import types
    from contextlib import nullcontext
    from llm_ontology.benchmarks import evaluation_generation

    adapter = _fake_adapter(prepared.root, "b2_testing_onto")
    for ident in prepared.ids:
        (prepared.root / "cases" / ident / "frozen_prompts/ft_onto/prompt.txt").write_text(
            prepared.prompt(ident, "ft_onto"))
    torch = types.SimpleNamespace(manual_seed=lambda s: None, inference_mode=nullcontext,
        cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setattr(matrix.batch, "runtime", lambda: types.SimpleNamespace(
        prompt_profile=None, max_new_tokens=4096, random_seed=42))
    loads, sent = [], []
    def generate_prediction(model, tokenizer, task, instruction, input_code, generation, on_prompt=None):
        prompt = matrix.format_inference_prompt(instruction, input_code)
        on_prompt(prompt)  # what the tokenizer received
        sent.append(prompt)
        raw = '{"testCase1":"assertTrue(true);","testCase2":"assertTrue(true);"}'
        return raw, {"raw_response": raw}
    monkeypatch.setattr(evaluation_generation, "generate_prediction", generate_prediction)
    monkeypatch.setattr(evaluation_generation, "load_eval_model", lambda *a: pytest.fail("reload"))
    monkeypatch.setattr(matrix.batch, "assemble", lambda *a: "class GeneratedBodyTests {}")

    class Tokenizer:
        def __call__(self, text):
            return {"input_ids": text.split()}
    monkeypatch.setattr(matrix.batch, "load_eval_model",
                        lambda model, inference: loads.append(model["adapter_path"]) or ("model", Tokenizer()))
    prepared.generate("ft_onto")
    assert loads == [str(adapter)]
    for ident, prompt in zip(prepared.ids, sent):
        out = prepared.out(ident, "ft_onto")
        assert matrix.read(out / "completion.json")["status"] == "assembled"
        frozen = (prepared.root / "cases" / ident / "frozen_prompts/ft_onto/prompt.txt").read_text()
        assert matrix.read(out / "dispatch.json")["request"]["prompt"] == prompt == frozen
        assert "<project-ontology>" in prompt
    assert matrix.read(prepared.root / "ft_onto-loaded_identity.json")["adapter"] == "b2_testing_onto"


def test_changed_adapter_blocks_the_arm_before_any_dispatch(prepared, monkeypatch):
    adapter = _fake_adapter(prepared.root, "b2_testing_v3")
    (adapter / "adapter_model.safetensors").write_text("retrained")
    monkeypatch.setattr(matrix.batch, "load_eval_model", lambda *a: pytest.fail("loaded a changed adapter"))
    with pytest.raises(ValueError, match="changed"):
        prepared.generate("ft_testing")
    assert not prepared.dispatches()
    assert (prepared.root / "ft_testing-stop.json").exists()


def test_rag_single_replays_the_frozen_request_without_retrieving(prepared, monkeypatch):
    """Retrieval runs once at freeze; generation sends the frozen request unchanged."""
    payload = {"model": matrix.batch.direct.MODELS["qwen_base"][0], "prompt": None, "stream": False,
               "options": matrix.batch.OPTIONS,
               "format": matrix.batch.TestingBodiesAnswer.model_json_schema()}
    for ident in prepared.ids:
        frozen = prepared.root / "cases" / ident / "frozen_prompts" / "rag_single"
        matrix.write(frozen / "request.json", {**payload, "prompt": (frozen / "prompt.txt").read_text()})
    monkeypatch.setattr(matrix.batch, "runtime", lambda: SimpleNamespace(
        generation_timeout_seconds=5, generation_model_digest="d"))
    monkeypatch.setattr(matrix.batch, "generate_rag", lambda *a, **kw: pytest.fail("retrieved again"))
    monkeypatch.setattr(matrix.batch, "assemble", lambda *a: "class GeneratedBodyTests {}")
    sent = []

    class Response:
        def __init__(self, body):
            self.body = json.dumps(body).encode()

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, **kwargs):
        if request.full_url.endswith("/api/tags"):
            return Response({"models": [{"name": payload["model"], "digest": "d"}]})
        sent.append(json.loads(request.data))
        return Response({"response": '{"testCase1":"assertTrue(true);","testCase2":"assertTrue(true);"}',
                         "done": True, "done_reason": "stop"})

    monkeypatch.setattr(matrix.batch, "urlopen", fake_urlopen)
    prepared.generate("rag_single")
    assert [s["prompt"] for s in sent] == ["frozen one/rag_single", "frozen two/rag_single"]
    assert all(s["keep_alive"] == 0 and s["options"] == matrix.batch.OPTIONS for s in sent)
    assert all(matrix.read(prepared.out(i, "rag_single") / "completion.json")["status"] == "assembled"
               for i in prepared.ids)


def test_rag_single_rejects_a_frozen_request_that_disagrees_with_the_frozen_prompt(prepared, monkeypatch):
    frozen = prepared.root / "cases" / "one" / "frozen_prompts" / "rag_single"
    matrix.write(frozen / "request.json", {"prompt": "something else"})
    monkeypatch.setattr(matrix.batch, "runtime", lambda: SimpleNamespace(
        generation_timeout_seconds=5, generation_model_digest="d"))
    prepared.generate("rag_single")
    assert not prepared.dispatches()
    assert matrix.read(prepared.root / "rag_single-stop.json")["status"] == "pre_dispatch_failure"


def _stopped_source(prepared, monkeypatch):
    """A frozen source run whose rag_single arm fail-stopped before dispatch on case two."""
    root = prepared.root
    java = root.parent / "java"
    java.write_text("java")
    files = {str((root / "cases" / i / "frozen_prompts" / a / "prompt.txt").absolute()): None
             for i in prepared.ids for a in matrix.ARMS}
    files = {p: matrix.batch.file_sha256(Path(p)) for p in files}
    matrix.write(root / "hf_file_pins.json", {})
    matrix.write(root / "freeze.json", {"protocol": matrix.PROTOCOL, "files": files,
        "sources": {}, "java": {str(java): matrix.batch.file_sha256(java)}, "maximum": prepared.maximum})
    monkeypatch.setattr(matrix.batch, "_generate_direct", fake_direct)
    monkeypatch.setattr(matrix.batch, "assemble", lambda *a: "class GeneratedBodyTests {}")
    prepared.generate("qwen_base")
    one = prepared.out("one", "rag_single")
    one.mkdir(parents=True)
    matrix.write(one / "dispatch.json", {"id": "one"})
    matrix.write(one / "completion.json", {"status": "assembled"})
    two = prepared.out("two", "rag_single")
    two.mkdir(parents=True)
    matrix.write(two / "failure.json", {"error": "Actual prompt differs from frozen prompt"})
    matrix.write(two / "completion.json", {"status": "pre_dispatch_failure"})
    matrix.write(root / "rag_single-stop.json", {"id": "two", "status": "pre_dispatch_failure"})
    entry = matrix.REPO / "pyproject.toml"
    monkeypatch.setattr(matrix.batch, "build_dependency_identity",
                        lambda c: {str(entry): matrix.batch.file_sha256(entry)})
    return root


def test_continuation_regenerates_only_uncharged_cells_of_the_stopped_arm(prepared, monkeypatch):
    source = _stopped_source(prepared, monkeypatch)
    target = source.parent / "continued"
    assert matrix.continue_arm(target, source, "rag_single") == ["two"]
    continuation = matrix.read(target / "continuation.json")
    assert continuation["arm"] == "rag_single" and continuation["reason"]["id"] == "two"
    assert not (target / "rag_single-stop.json").exists()
    assert not (target / "cases/two/predictions/rag_single").exists()
    assert (target / "cases/one/predictions/rag_single/completion.json").exists()
    assert (target / "cases/two/predictions/qwen_base/generated.java").exists()
    continued = matrix.Matrix(target)
    continued.verify()
    sent = []
    monkeypatch.setattr(matrix.batch, "replay_frozen_request", lambda c, frozen, ledger: (
        sent.append(frozen.parent.parent.name), ledger.charge({"prompt": (frozen / "prompt.txt").read_text()}),
        (ledger.out / "raw.txt").write_text('{"testCase1":"assertTrue(true);","testCase2":"assertTrue(true);"}'),
        {})[-1])
    continued.generate("rag_single")
    assert sent == ["two"]
    assert matrix.read(continued.out("two", "rag_single") / "completion.json")["status"] == "assembled"
    with pytest.raises(ValueError, match="already exists"):
        matrix.continue_arm(target, source, "rag_single")
    with pytest.raises(ValueError, match="fail-stopped"):
        matrix.continue_arm(source.parent / "other", source, "qwen_base")


def test_continuation_refuses_an_interrupted_charged_cell(prepared, monkeypatch):
    source = _stopped_source(prepared, monkeypatch)
    (prepared.out("one", "rag_single") / "completion.json").unlink()
    with pytest.raises(ValueError, match="Interrupted"):
        matrix.continue_arm(source.parent / "continued", source, "rag_single")
    assert not (source.parent / "continued").exists()
