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
    for path in Path("configs/finetuning").glob("training_*_wsl.yaml"):
        config = read_yaml(path)
        root = "data/processed/v3_onto/" if path.stem.endswith("_onto_wsl") else "data/processed/v3/"
        assert all(config["dataset"][k].startswith(root) for k in ("train_file", "val_file", "test_file"))
        model = read_yaml(Path(config["experiment"]["model_config"]))
        assert model["runtime"]["max_seq_length"] >= 8192


def test_onto_training_configs_differ_from_v3_only_in_data_and_outputs():
    for task in ("testing", "refactoring"):
        v3 = read_yaml(Path(f"configs/finetuning/training_b2_{task}_wsl.yaml"))
        onto = read_yaml(Path(f"configs/finetuning/training_b2_{task}_onto_wsl.yaml"))
        assert onto["run"] == v3["run"]
        assert {k: v for k, v in onto["experiment"].items() if k not in {"name", "description"}} == \
            {k: v for k, v in v3["experiment"].items() if k not in {"name", "description"}}
        assert onto["dataset"] == {k: v.replace("/v3/", "/v3_onto/") for k, v in v3["dataset"].items()}
