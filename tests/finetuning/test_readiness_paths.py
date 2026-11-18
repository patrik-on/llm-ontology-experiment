from pathlib import Path

from llm_ontology.finetuning.training.readiness import check_training_config

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs/finetuning/training_b2_testing_onto_wsl.yaml"


def test_readiness_expands_home_and_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(REPO)
    failures = []
    check_training_config(CONFIG, failures)
    assert not (REPO / "~").exists()
    assert not (tmp_path / "home").exists()
    assert not any("Final adapter" in f for f in failures)


def test_readiness_refuses_to_overwrite_a_trained_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(REPO)
    adapter = tmp_path / "experiments/llm-ontology-v3/b2_testing_onto/checkpoints/final_adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_model.safetensors").write_text("trained")
    failures = []
    check_training_config(CONFIG, failures)
    assert any("would be overwritten" in f for f in failures)
