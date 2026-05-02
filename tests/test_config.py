from pathlib import Path

from llm_ontology.core.config import load_experiment_config


ROOT = Path(__file__).resolve().parents[1]


def test_load_experiment_config_merges_base() -> None:
    config = load_experiment_config(ROOT / "configs/experiments/b1_shared_ft.yaml")

    assert config["experiment"]["name"] == "b1_shared_ft"
    assert config["experiment"]["domain"] == "combined"
    assert config["model"]["base_model"] == "codellama/CodeLlama-7b-Instruct-hf"
    assert config["lora"]["r"] == 16
