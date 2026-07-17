from __future__ import annotations

from pathlib import Path

from llm_ontology.core.config import read_yaml


MODEL_CONFIGS = (
    Path("configs/models/qwen25_coder_7b_hf.yaml"),
    Path("configs/models/qwen25_coder_7b_hf_wsl.yaml"),
    Path("configs/models/qwen25_coder_7b_ollama.yaml"),
)


def test_required_model_configs_exist_and_have_runtime() -> None:
    for path in MODEL_CONFIGS:
        config = read_yaml(path)
        assert config["model"]["name"]
        assert config["runtime"]


def test_training_configs_reference_existing_model_configs() -> None:
    for path in Path("configs/finetuning").glob("training_*.yaml"):
        config = read_yaml(path)
        referenced = Path(config["experiment"]["model_config"])
        assert referenced.exists(), f"{path} references missing model config {referenced}"


def test_future_retrieval_experiments_are_disabled_and_train_only() -> None:
    for path in (
        Path("configs/experiments/rag/template.yaml"),
        Path("configs/experiments/multi_rag/template.yaml"),
    ):
        config = read_yaml(path)
        assert config["experiment"]["enabled"] is False
        assert config["retrieval"]["allowed_splits"] == ["train"]
