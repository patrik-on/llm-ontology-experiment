"""Direct/no-retrieval helpers shared by Methods2Test evaluations."""
from pathlib import Path
from llm_ontology.benchmarks.java_execution import file_sha256
from llm_ontology.inference.experiment_runner import RagExperimentConfig
from llm_ontology.retrieval.token_budget import HuggingFaceTokenCounter
PROTOCOL = "methods2test_direct_v1"
MODELS = {"qwen_base": ("qwen2.5-coder:7b", "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364", None)}
TOKENIZER = Path("/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct")

class ForbiddenStore:
    def __getattr__(self, name):
        raise AssertionError(f"Direct pilot forbids vector-store access: {name}")

def counter():
    return HuggingFaceTokenCounter(model_identifier=str(TOKENIZER),
                                  model_revision=file_sha256(TOKENIZER / "tokenizer.json"))

def experiment(output, arm, tokens):
    return RagExperimentConfig(
        enabled=True, baseline_id=PROTOCOL, requested_task="testing", retrieval_mode="no_rag",
        dataset_version="methods2test-eval", embedding_model="none",
        embedding_revision="not_used", llm_model=MODELS[arm][0], generation_max_tokens=4096,
        tokenizer_model=tokens.model_identifier, tokenizer_revision=tokens.model_revision,
        total_context_tokens=32768, reserved_output_tokens=4096, safety_margin_tokens=256,
        runtime_context_tokens=32768, fail_on_prompt_budget_exceeded=True,
        results_path=output / "experiment.jsonl", prompt_artifacts_dir=output / "prompts")
