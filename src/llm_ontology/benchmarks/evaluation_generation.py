"""Shared local HF/RAG generation; no dataset checkout or benchmark CLI."""
from __future__ import annotations
import gc
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from llm_ontology.benchmarks.evaluation_runtime import EvaluationRuntime
from llm_ontology.benchmarks.java_execution import file_sha256, write_json
from llm_ontology.core.config import read_yaml
from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentConfig, RagExperimentRunner
from llm_ontology.evaluation.hf_inference import generate_prediction, load_eval_model, selected_models
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.structured_output import TestingAnswer, TestingBodiesAnswer
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.factory import create_llm_provider, create_vector_store
from llm_ontology.retrieval.models import RetrievalMode
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter
ARMS = ("ft_testing", "rag_single", "rag_multi")
PROTOCOL = "java_evaluation_runtime_v1"

def build_dependency_identity(config: EvaluationRuntime, *, source_root: Path | None = None) -> dict[str, str]:
    """Hash actual scoped Python source bytes, including dirty/untracked shared code."""
    package = source_root or Path(__file__).resolve().parent.parent
    paths = set(package.rglob("*.py"))
    paths.update((config.retrieval_config, config.hf_models_config))
    runtime_config = Path("configs/benchmarks/java_evaluation_runtime_v1.yaml")
    if runtime_config.is_file():
        paths.add(runtime_config)
    project_metadata = package.parent.parent / "pyproject.toml"
    if project_metadata.is_file():
        paths.add(project_metadata)
    return {str(path.resolve()): file_sha256(path) for path in sorted(paths)}

def generation_failure_payload(exc: Exception, *, case_sha256: str, arm: str) -> dict[str, Any]:
    return {"status": "generation_failure", "error": str(exc), "case_sha256": case_sha256,
            "arm": arm, "diagnostic_only": True,
            "structured_output_attempts": [attempt.model_dump(mode="json")
                                           for attempt in getattr(exc, "attempts", [])],
            "failure_metadata": getattr(exc, "failure_metadata", {})}

def hf_identity(config: EvaluationRuntime, *, hashes: bool = True) -> dict[str, Any]:
    models = read_yaml(config.hf_models_config)
    model = selected_models(models, config.hf_model_name)[0]
    root = Path(model["model_path"]).expanduser().resolve()
    if not model.get("adapter_path") or str(model["adapter_path"]).lower() in {"baseline", "none", "null"}:
        raise ValueError("The FT arm requires a configured local PEFT adapter, not a baseline model.")
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
    if training.get("experiment") != model["name"]:
        raise ValueError(f"Adapter at {adapter} was trained as {training.get('experiment')!r}, "
                         f"not {model['name']!r}.")
    if Path(training["train_file"]) not in config.training_sources:
        raise ValueError("Leakage inputs do not include the selected adapter training-summary source.")
    if not training.get("val_file"):
        raise ValueError("Selected adapter has no explicit validation/checkpoint-selection source lineage.")
    validation = Path(training["val_file"])
    if validation not in config.validation_sources or validation not in config.checkpoint_selection_sources:
        raise ValueError("Leakage inputs must include the adapter validation/checkpoint-selection source.")
    identities = {}
    for path in files:
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"Incomplete local model: {path}")
        identities[str(path)] = {"bytes": path.stat().st_size,
                                 "sha256": file_sha256(path) if hashes else "not_computed"}
    return {"model": model, "inference": models["inference"], "files": identities,
            "prompt_contract": "instruction-v1-raw-java-jupiter-request",
            "output_contract": "raw-java-only-no-semantic-repair"}


def verify_hf_identity(identity: dict[str, Any]) -> dict[str, Any]:
    """Re-hash every frozen base-model and adapter file just before the model is loaded.

    The returned identity is the one to load from, so an FT arm cannot generate with an
    adapter or base model other than the one frozen for it."""
    for path, pin in identity["files"].items():
        if file_sha256(Path(path)) != pin["sha256"]:
            raise ValueError("Frozen model/adapter file changed: " + path)
    adapter = Path(identity["model"]["adapter_path"]).expanduser().resolve()
    if str(adapter / "adapter_model.safetensors") not in identity["files"]:
        raise ValueError("Adapter path differs from the frozen adapter files")
    return identity

def generate_ft(config: EvaluationRuntime, case: ExperimentCase, output: Path, *,
                loaded_model: tuple[Any, Any] | None = None,
                model_identity: dict[str, Any] | None = None, before_generation=None) -> dict[str, Any]:
    import torch
    # Local paths only, no tokenizer/model/adapter downloads or remote custom code.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if config.prompt_profile:
        from llm_ontology.inference.prompting.testing_full_class_v2 import apply_profile
        case = apply_profile(case, envelope="ft")
    identity = model_identity or hf_identity(config)
    write_json(output / "model_identity.json", identity)
    inference = {**identity["inference"], "local_files_only": True, "trust_remote_code": False}
    prompt = format_inference_prompt(case.instruction, case.input_text)
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(output / "prompt_identity.json", {
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "instruction_sha256": hashlib.sha256(case.instruction.encode()).hexdigest(),
        "template": "instruction-v1", "case_metadata": case.metadata,
        "random_seed": config.random_seed, "max_new_tokens": config.max_new_tokens})
    model, tokenizer = loaded_model or load_eval_model(identity["model"], inference)
    try:
        prompt_tokens = len(tokenizer(prompt)["input_ids"])
        if prompt_tokens + config.max_new_tokens + 256 > 32768:
            raise ValueError("FT prompt exceeds declared context; do not silently truncate.")
        torch.manual_seed(config.random_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.random_seed)
        with torch.inference_mode():
            prediction, generation = generate_prediction(
                model, tokenizer, "testing", case.instruction, case.input_text,
                {"max_new_tokens": config.max_new_tokens, "do_sample": False,
                 "top_p": 0.9, "repetition_penalty": 1.0}, on_prompt=before_generation)
        (output / "raw.txt").write_text(generation.get("raw_response", prediction), encoding="utf-8")
        write_json(output / "generation_metadata.json", generation)
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
        return {"source": source, "prompt_contract": ("instruction-v1+" + case.metadata["prompt_profile"]
                if case.metadata.get("prompt_profile") else identity["prompt_contract"]),
                "model_identity": identity, "generation": generation, "random_seed": config.random_seed,
                "prompt_tokens": prompt_tokens,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    finally:
        if loaded_model is None:
            del model, tokenizer
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

def generate_rag(config: EvaluationRuntime, case: ExperimentCase, output: Path,
                 arm: str, audit: dict[str, Any], *, body_profile: bool = False, opener=None) -> dict[str, Any]:
    if config.prompt_profile:
        from llm_ontology.inference.prompting.testing_full_class_v2 import apply_profile
        case = apply_profile(case, envelope="rag")
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
    provider = create_llm_provider(rag.llm.model_copy(update={"max_tokens": config.max_new_tokens,
        "timeout_seconds": config.generation_timeout_seconds}))
    if opener is not None:
        provider._opener = opener
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
        enabled=True, baseline_id=case.metadata.get("protocol", PROTOCOL), requested_task="testing", retrieval_mode=mode,
        collection="mixed" if arm == "rag_single" else None,
        collections=[] if arm == "rag_single" else ["testing_db", "refactoring_db"],
        dataset_version=case.metadata.get("dataset_version", "java-evaluation"), embedding_model=rag.embeddings.model,
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
        fail_on_prompt_budget_exceeded=True, structured_retries=0,
        **body_options(body_profile, profile=case.metadata.get("prompt_profile")))
    write_json(output / "schema.json", (TestingBodiesAnswer if body_profile else TestingAnswer).model_json_schema())
    write_json(output / "index_manifests.json", manifests)
    write_json(output / "effective_generation.json", {
        "timeout_seconds": provider.timeout_seconds,
        "seed": provider.seed, "temperature": provider.temperature, "top_p": provider.top_p,
        "max_tokens": provider.max_tokens, "context_window_tokens": provider.context_window_tokens,
        "protocol": case.metadata.get("protocol", PROTOCOL), "case_metadata": case.metadata})
    record = runner.run_case(exp, case)
    if record.generation_model_digest != generation_digest:
        raise ValueError("Generation model digest changed during run.")
    source = (record.response if body_profile
              else TestingAnswer.model_validate_json(record.response).generated_tests)
    return {"source": source, "prompt_contract": ("canonical-json-v2+" + case.metadata["prompt_profile"]
            if case.metadata.get("prompt_profile") else "canonical-json-v2-junit5"),
            "experiment_record": record.model_dump(mode="json"), "leakage_audit": audit}

def body_options(enabled: bool, *, profile: str | None = None) -> dict[str, Any]:
    if not enabled:
        return {}
    if profile == "testing-bodies-one-shot-v2":
        from llm_ontology.inference.prompting.testing_bodies_one_shot_v2 import BodyPromptBuilder
    else:
        from llm_ontology.inference.prompting.testing_bodies_v1 import BodyPromptBuilder
    return {"prompt_builder": BodyPromptBuilder(), "structured_answer_model": TestingBodiesAnswer}
