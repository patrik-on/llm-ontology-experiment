from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_CONFIG = ROOT / "configs" / "evaluation" / "eval_models_v2_only.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "adapters"
REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors", "tokenizer_config.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lora_models(config_path: Path) -> list[dict[str, Any]]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return [model for model in payload.get("models", []) if model.get("type") == "lora"]


def validate_adapter(adapter_dir: Path) -> None:
    missing = [filename for filename in REQUIRED_FILES if not (adapter_dir / filename).exists()]
    if missing:
        raise FileNotFoundError(f"{adapter_dir} is missing required files: {', '.join(missing)}")


def zip_adapter(model_name: str, adapter_dir: Path, output_dir: Path) -> dict[str, Any]:
    validate_adapter(adapter_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{model_name}_final_adapter.zip"

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file_path in sorted(adapter_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(adapter_dir))

    checksum = sha256_file(zip_path)
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sha_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")

    return {
        "model_name": model_name,
        "source_adapter_dir": str(adapter_dir),
        "zip_file": str(zip_path),
        "zip_file_name": zip_path.name,
        "sha256_file": str(sha_path),
        "sha256": checksum,
        "size_bytes": zip_path.stat().st_size,
        "required_files": list(REQUIRED_FILES),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package v2 LoRA adapters as ZIP files for external handoff.")
    parser.add_argument("--models-config", default=str(DEFAULT_MODELS_CONFIG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    config_path = Path(args.models_config)
    output_dir = Path(args.output_dir)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "models_config": str(config_path),
        "output_dir": str(output_dir),
        "adapters": [],
    }

    for model in load_lora_models(config_path):
        model_name = str(model["name"])
        adapter_path = Path(str(model["adapter_path"]))
        print(f"Packaging {model_name}: {adapter_path}")
        manifest["adapters"].append(zip_adapter(model_name, adapter_path, output_dir))

    manifest_path = output_dir / "v2_adapter_zip_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote manifest: {manifest_path}")
    for item in manifest["adapters"]:
        size_mb = item["size_bytes"] / (1024 * 1024)
        print(f"- {item['zip_file_name']}: {size_mb:.1f} MB, sha256={item['sha256']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Adapter packaging failed: {exc}") from exc
