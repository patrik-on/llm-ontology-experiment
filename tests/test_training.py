from llm_ontology.training.sampler import balanced_domain_sample
from llm_ontology.training.trainer import dry_run_training


def test_balanced_domain_sample() -> None:
    records = [
        {"domain": "refactoring", "id": 1},
        {"domain": "refactoring", "id": 2},
        {"domain": "testing", "id": 3},
    ]

    sampled = balanced_domain_sample(records)

    assert len(sampled) == 2
    assert {record["domain"] for record in sampled} == {"refactoring", "testing"}


def test_dry_run_training_returns_paths(tmp_path) -> None:
    config = {
        "experiment": {"name": "x"},
        "data": {"train_file": str(tmp_path / "train.jsonl")},
        "output": {
            "adapter_dir": str(tmp_path / "adapters"),
            "checkpoint_dir": str(tmp_path / "checkpoints"),
            "result_dir": str(tmp_path / "results"),
        },
    }

    result = dry_run_training(config)

    assert result["experiment"] == "x"
    assert (tmp_path / "adapters").exists()
    assert (tmp_path / "checkpoints").exists()
    assert (tmp_path / "results").exists()
