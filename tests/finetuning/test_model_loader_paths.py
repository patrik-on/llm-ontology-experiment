from pathlib import Path

from llm_ontology.core.config import read_yaml
from llm_ontology.models.loader import model_path


def test_model_path_accepts_both_config_schemas():
    assert model_path({"model": {"base_model": "hub/id"}}) == "hub/id"
    hf = {"model": {"name": "/m/qwen", "tokenizer_name": "/m/tok"}}
    assert model_path(hf) == "/m/qwen" and model_path(hf, tokenizer=True) == "/m/tok"
    for path in Path("configs/shared/models").glob("*_hf*.yaml"):
        assert model_path(read_yaml(path))


def test_v3_training_configs_use_v3_data_and_a_non_truncating_budget():
    for path in Path("configs/finetuning").glob("training_*_v3_wsl.yaml"):
        config = read_yaml(path)
        assert config["dataset"]["train_file"].startswith("data/processed/v3/")
        model = read_yaml(Path(config["experiment"]["model_config"]))
        assert model["runtime"]["max_seq_length"] >= 8192
