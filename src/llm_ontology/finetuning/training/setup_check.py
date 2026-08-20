from __future__ import annotations

from pathlib import Path

from llm_ontology.core.config import read_yaml
from llm_ontology.finetuning.dataset_loader import load_jsonl, validate_example
from llm_ontology.finetuning.prompt_formatter import format_inference_prompt, format_training_prompt


TRAINING_CONFIGS = (
    Path("configs/finetuning/training_b1_shared.yaml"),
    Path("configs/finetuning/training_b2_refactoring.yaml"),
    Path("configs/finetuning/training_b2_testing.yaml"),
)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"[FAIL] {message}")


def check_path(path: Path, description: str, failures: list[str]) -> bool:
    if path.exists():
        ok(f"{description}: {path}")
        return True
    fail(f"Missing {description}: {path}", failures)
    return False


def check_training_config(config_path: Path, failures: list[str]) -> None:
    if not check_path(config_path, "training config", failures):
        return
    config = read_yaml(config_path)
    experiment_name = config.get("experiment", {}).get("name", config_path.stem)
    check_path(Path(config["experiment"]["model_config"]), f"{experiment_name} model config", failures)
    check_path(Path(config["experiment"]["lora_config"]), f"{experiment_name} LoRA config", failures)

    for key in ("train_file", "val_file", "test_file"):
        dataset_path = Path(config["dataset"][key])
        if not check_path(dataset_path, f"{experiment_name} {key}", failures):
            continue
        records = load_jsonl(dataset_path)
        if not records:
            fail(f"{dataset_path} has no records", failures)
            continue
        if not validate_example(records[0]):
            fail(f"First record in {dataset_path} is missing instruction/input/output", failures)
            continue
        training_prompt = format_training_prompt(records[0])
        inference_prompt = format_inference_prompt(records[0]["instruction"], records[0]["input"])
        if "### Response:" in training_prompt and training_prompt.endswith(records[0]["output"]):
            ok(f"Prompt formatter works for {dataset_path}")
        else:
            fail(f"Training prompt formatter produced unexpected output for {dataset_path}", failures)
        if inference_prompt.endswith("### Response:\n"):
            ok(f"Inference prompt formatter works for {dataset_path}")
        else:
            fail(f"Inference prompt formatter produced unexpected output for {dataset_path}", failures)

    for key in ("output_dir", "logging_dir", "results_dir"):
        check_path(Path(config["output"][key]), f"{experiment_name} {key}", failures)


def main() -> None:
    failures: list[str] = []
    print("Fine-tuning setup check")
    for config_path in TRAINING_CONFIGS:
        check_training_config(config_path, failures)
    if failures:
        print(f"\nFinished with {len(failures)} failure(s).")
        raise SystemExit(1)
    print("\nFine-tuning setup looks ready.")


if __name__ == "__main__":
    main()
