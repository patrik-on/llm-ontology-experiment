from llm_ontology.core.config import load_experiment_config


def test_load_experiment_config_merges_base(tmp_path) -> None:
    base = tmp_path / "base.yaml"
    base.write_text(
        """
model:
  base_model: "codellama/CodeLlama-7b-Instruct-hf"
lora:
  r: 16
""".strip(),
        encoding="utf-8",
    )
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        """
defaults:
  - base.yaml

experiment:
  name: sample_ft
  domain: combined

data:
  train_file: data/processed/combined/train.jsonl
  val_file: data/processed/combined/val.jsonl
  test_file: data/processed/combined/test.jsonl

output:
  adapter_dir: artifacts/adapters/sample_ft
  checkpoint_dir: artifacts/checkpoints/sample_ft
  result_dir: results/sample_ft
""".strip(),
        encoding="utf-8",
    )

    config = load_experiment_config(config_path)

    assert config["experiment"]["name"] == "sample_ft"
    assert config["experiment"]["domain"] == "combined"
    assert config["model"]["base_model"] == "codellama/CodeLlama-7b-Instruct-hf"
    assert config["lora"]["r"] == 16
