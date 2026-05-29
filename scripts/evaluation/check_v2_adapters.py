from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors", "tokenizer_config.json")
V2_ADAPTERS = {
    "b2_testing_v2": Path("/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter"),
    "b2_refactoring_v2": Path("/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter"),
    "b1_shared_v2": Path("/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter"),
}


def load_lora_adapters_from_config(config_path: str | Path) -> dict[str, Path]:
    with Path(config_path).open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = yaml.safe_load(handle) or {}

    adapters: dict[str, Path] = {}
    for model_config in payload.get("models", []):
        if model_config.get("type") != "lora":
            continue
        adapter_path = model_config.get("adapter_path")
        if adapter_path:
            adapters[str(model_config["name"])] = Path(str(adapter_path))
    return adapters


def check_adapters(adapters: dict[str, Path]) -> None:
    if not adapters:
        raise SystemExit("No LoRA adapters found to check.")

    missing: list[str] = []
    for model_name, adapter_dir in adapters.items():
        print(f"{model_name}: {adapter_dir}")
        for filename in REQUIRED_FILES:
            path = adapter_dir / filename
            if path.exists():
                print(f"  [OK] {filename}")
            else:
                print(f"  [MISSING] {filename}")
                missing.append(str(path))
    if missing:
        raise SystemExit("Missing required v2 adapter files:\n" + "\n".join(missing))
    print("\nV2 adapter file check OK.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check that LoRA adapter directories contain required files.")
    parser.add_argument(
        "--models-config",
        help="Optional evaluation models YAML. When provided, all LoRA adapter_path entries are checked.",
    )
    args = parser.parse_args()

    adapters = load_lora_adapters_from_config(args.models_config) if args.models_config else V2_ADAPTERS
    check_adapters(adapters)


if __name__ == "__main__":
    main()
