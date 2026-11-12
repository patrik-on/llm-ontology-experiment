"""Pre-dispatch guards for the opt-in three-call body demonstration comparison."""
from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.approaches import RetrievedContext
from llm_ontology.benchmarks.defects4j_execution import clean_env, evaluate_revision, file_sha256, run_process, write_json
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as demo
from llm_ontology.inference.prompting.testing_bodies_v1 import CONTRACT, sha
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.structured_output import TestingBodiesAnswer
from llm_ontology.retrieval.query import build_retrieval_query

OLD = Path("artifacts/evaluation/runs/qwen-shared-bodies-v1-20261112")
ARMS = ("qwen_base", "ft_testing", "rag_single")


def read(path):
    return json.loads(path.read_text())


def preflight(root, c, case):
    """No model generation, index mutation, subject build or new evaluation pipeline."""
    files = []
    for name, content in (("demo/Labels.java", demo.DEMO_PRODUCTION),
                          ("demo/scaffold.java", demo.DEMO_SCAFFOLD),
                          ("demo/answer.json", demo.DEMO_JSON),
                          ("demo/GeneratedBodyTests.java", demo.demo_source()),
                          ("demo/block.txt", demo.DEMO_BLOCK)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        files.append(name)
    classes = root / "demo/production-classes"
    classes.mkdir()
    compile_result = run_process([str(c.java_home / "bin/javac"), "-proc:none", "-d", str(classes),
        str(root / "demo/Labels.java")], root, clean_env(root / "demo/home", c.java_home),
        c.timeout_seconds, root / "demo/production-compile.log")
    if compile_result.get("returncode") != 0:
        raise ValueError("Synthetic demonstration production compile failed.")
    revision = {"bin_classes": str(classes), "dependencies": []}
    result = evaluate_revision(demo.demo_source(), revision, output=root / "demo/evaluation",
        java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256, timeout=c.timeout_seconds)
    if result["status"] != "passed" or result["console_summary"]["tests_started"] != 2:
        raise ValueError("Solved synthetic body demonstration failed.")
    oldcase = read(OLD / "case.json")
    for key in ("input_text", "structured_identity", "requirements", "project_context"):
        if getattr(case, key) != oldcase[key]:
            raise ValueError("Target production/scaffold/context changed: " + key)
    if case.instruction != oldcase["instruction"] + demo.DEMO_BLOCK or oldcase["instruction"] != CONTRACT:
        raise ValueError("Change is not exactly one appended demo block.")
    for name in ("scaffold.java", "schema.json", "index_identity.json", "hf_identity.json", "ollama_model.json"):
        equal = (read(root / name) == read(OLD / name) if name.endswith(".json")
                 else (root / name).read_bytes() == (OLD / name).read_bytes())
        if not equal:
            raise ValueError("Frozen identity differs from v1: " + name)
    oldrag = read(OLD / "predictions/rag_single/generation.json")["experiment_record"]
    query = build_retrieval_query(strategy=oldrag["configuration"]["retrieval_query_strategy"], task="testing",
        input_text=case.input_text, requirements=case.requirements, structured_identity=case.structured_identity)
    trace = oldrag["retrieval_trace"]
    if query != trace["query"] or demo.DEMO_BLOCK in query:
        raise ValueError("Single-RAG query changed or demonstration entered retrieval.")
    ids = trace["prompt_document_ids"]
    documents = {d["document_id"]: d for d in trace["retrieved_documents"]}
    contexts = tuple(RetrievedContext(document_id=i, content=documents[i]["content"],
        source=str(documents[i]["metadata"].get("source", documents[i]["collection"])),
        score=documents[i].get("reranking_score") if documents[i].get("reranking_score") is not None else documents[i]["score"],
        metadata={**documents[i]["metadata"], "collection": documents[i]["collection"]}) for i in ids)
    prompts = {}
    for arm in ARMS:
        if arm == "ft_testing":
            instruction = case.instruction + "\n" + case.requirements + "\n" + case.project_context + "\nJSON schema: " + json.dumps(TestingBodiesAnswer.model_json_schema(), sort_keys=True)
            prompt = format_inference_prompt(instruction, case.input_text)
            oldprompt = (OLD / "predictions" / arm / "prompt.txt").read_text()
        else:
            prompt = demo.BodyPromptBuilder().build(task="testing", instruction=case.instruction,
                input_text=case.input_text, requirements=case.requirements, project_context=case.project_context,
                contexts=contexts if arm == "rag_single" else (), approach="rag" if arm == "rag_single" else "direct").text
            record = read(OLD / "predictions" / arm / "generation.json")["experiment_record"]
            oldprompt = Path(record["prompt_artifact_path"]).read_text()
        if prompt.count(demo.DEMO_BLOCK) != 1 or prompt.replace(demo.DEMO_BLOCK, "") != oldprompt:
            raise ValueError("Base prompt does not match v1 after stripping ONLY demo: " + arm)
        name = "frozen-prompts/" + arm + ".txt"
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(prompt)
        files.append(name)
        prompts[arm] = {"sha256": sha(prompt), "baseline_sha256": sha(oldprompt), "base_prompt_equal": True}
    oldpins = read(OLD / "freeze.json")["pins"]
    write_json(root / "preflight.json", {"demo_passed": True, "demo_tests_started": 2,
        "demo_source_sha256": sha(demo.demo_source()), "production_compile": compile_result,
        "query_sha256": sha(query), "prompt_document_ids": ids, "prompts": prompts,
        "prepared_sha256": oldpins["prepared"], "scaffold_sha256": file_sha256(root / "scaffold.java"),
        "baseline_source_identity": oldpins["sources"], "historical_run": str(OLD),
        "evidence_freeze": "Reconstructed from old trace; dispatch rejects any actual rendered evidence/prompt difference.",
        "demo_role": "synthetic-only; never indexed or trained"})
    return [*files, "preflight.json"]


def verify_request(root, arm, request):
    prompt = request["prompt"]
    if prompt != (root / "frozen-prompts" / (arm + ".txt")).read_text():
        raise ValueError("Actual prompt/evidence differs from frozen one-shot preflight; no dispatch.")
    if prompt.count(demo.DEMO_BLOCK) != 1:
        raise ValueError("Expected exactly one identical demonstration.")
