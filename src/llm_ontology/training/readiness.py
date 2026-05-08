from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_ontology.core.config import read_yaml
from llm_ontology.finetuning.dataset_loader import load_jsonl, validate_example


DEFAULT_TRAINING_CONFIGS = (
    Path("configs/finetuning/training_b2_testing.yaml"),
    Path("configs/finetuning/training_b2_refactoring.yaml"),
    Path("configs/finetuning/training_b1_shared.yaml"),
)
TRAINING_SCRIPT = Path("scripts/training/train_finetuning.py")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"[FAIL] {message}")


def check_path(path: Path, description: str, failures: list[str], directory: bool = False) -> bool:
    exists = path.is_dir() if directory else path.exists()
    if exists:
        ok(f"{description}: {path}")
        return True
    fail(f"Missing {description}: {path}", failures)
    return False


def existing_path(path: Path) -> Path:
    if path.exists():
        return path
    text = path.as_posix()
    parts = text.split("/")
    if len(parts) > 3 and parts[0] == "" and parts[1] == "mnt" and len(parts[2]) == 1:
        windows_path = Path(f"{parts[2].upper()}:/" + "/".join(parts[3:]))
        if windows_path.exists():
            ok(f"Using Windows view for WSL path {path}: {windows_path}")
            return windows_path
    return path


def check_local_model(model_config: dict[str, Any], failures: list[str]) -> None:
    model_dir = existing_path(Path(model_config["model"]["name"]))
    if not check_path(model_dir, "local model directory", failures, directory=True):
        return
    check_path(model_dir / "config.json", "model config.json", failures)
    if (model_dir / "tokenizer.json").exists() or (model_dir / "tokenizer_config.json").exists():
        ok("Tokenizer file exists")
    else:
        fail(f"Missing tokenizer.json or tokenizer_config.json in {model_dir}", failures)
    safetensors = list(model_dir.glob("*.safetensors"))
    if safetensors:
        ok(f"Found {len(safetensors)} .safetensors file(s)")
    else:
        fail(f"No .safetensors files found in {model_dir}", failures)


def check_dataset(path: Path, failures: list[str]) -> None:
    if not check_path(path, "dataset file", failures):
        return
    try:
        records = load_jsonl(path)
    except Exception as exc:
        fail(f"Could not read dataset {path}: {exc}", failures)
        return
    if not records:
        fail(f"Dataset is empty: {path}", failures)
        return
    if validate_example(records[0]):
        ok(f"First record is valid: {path}")
    else:
        fail(f"First record is missing instruction/input/output: {path}", failures)


def check_lora_config(lora_config_path: Path, failures: list[str]) -> dict[str, Any] | None:
    if not check_path(lora_config_path, "LoRA config", failures):
        return None
    lora_config = read_yaml(lora_config_path)
    if lora_config.get("quantization", {}).get("load_in_4bit") is True:
        ok("QLoRA 4-bit quantization is enabled")
    else:
        fail(f"{lora_config_path} must have quantization.load_in_4bit: true", failures)
    return lora_config


def check_training_config(config_path: Path, failures: list[str]) -> None:
    if not check_path(config_path, "training config", failures):
        return
    config = read_yaml(config_path)

    model_config_path = Path(config["experiment"]["model_config"])
    lora_config_path = Path(config["experiment"]["lora_config"])
    if not check_path(model_config_path, "model config referenced by training config", failures):
        return
    model_config = read_yaml(model_config_path)
    check_local_model(model_config, failures)
    check_lora_config(lora_config_path, failures)

    for key in ("train_file", "val_file", "test_file"):
        check_dataset(Path(config["dataset"][key]), failures)

    for key in ("output_dir", "logging_dir", "results_dir"):
        check_path(Path(config["output"][key]), f"experiment {key}", failures, directory=True)

    final_adapter_dir = Path(config["output"]["final_adapter_dir"])
    final_adapter_dir.parent.mkdir(parents=True, exist_ok=True)
    ok(f"Final adapter parent exists: {final_adapter_dir.parent}")

    run = config.get("run", {})
    if run.get("dry_run") is False:
        ok(f"{config_path.name} is configured for real run (dry_run=false)")
    else:
        fail(f"{config_path.name} is not configured for real run (dry_run should be false)", failures)
    for key in ("max_train_samples", "max_val_samples", "max_steps"):
        if run.get(key) is None:
            ok(f"{config_path.name} uses full-run null value for {key}")
        else:
            fail(f"{config_path.name} should set {key}: null for full training", failures)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check that a LoRA/QLoRA fine-tuning config is ready.")
    parser.add_argument("--config", default=None, help="Optional single training config to validate, e.g. *_wsl.yaml.")
    args = parser.parse_args()

    failures: list[str] = []
    print("Fine-tuning readiness check")
    if args.config:
        config_paths = (Path(args.config),)
    else:
        print("[INFO] No --config provided. Checking default Windows configs.")
        print("[INFO] For WSL, prefer: python scripts/training/check_finetuning_ready.py --config configs/finetuning/<experiment>_wsl.yaml")
        config_paths = DEFAULT_TRAINING_CONFIGS

    for config_path in config_paths:
        check_training_config(config_path, failures)
    check_path(TRAINING_SCRIPT, "fine-tuning script", failures)

    if failures:
        print(f"\nFine-tuning setup has {len(failures)} issue(s).")
        raise SystemExit(1)
    print("\nFine-tuning setup is ready.")


if __name__ == "__main__":
    main()
