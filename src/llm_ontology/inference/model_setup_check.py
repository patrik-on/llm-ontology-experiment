from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from llm_ontology.core.config import read_yaml


HF_CONFIG = Path("configs/models/qwen25_coder_7b_hf.yaml")
OLLAMA_CONFIG = Path("configs/models/qwen25_coder_7b_ollama.yaml")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def check_file(path: Path, description: str) -> bool:
    if path.exists():
        ok(f"{description}: {path}")
        return True
    warn(f"Missing {description}: {path}")
    return False


def check_hf_model() -> None:
    if not check_file(HF_CONFIG, "Hugging Face model config"):
        return
    config = read_yaml(HF_CONFIG)
    model_dir = Path(config["model"]["name"])
    if not model_dir.exists():
        warn(f"Local Hugging Face model directory is missing: {model_dir}")
        return
    ok(f"Local Hugging Face model directory exists: {model_dir}")
    check_file(model_dir / "config.json", "HF config.json")
    if (model_dir / "tokenizer_config.json").exists() or (model_dir / "tokenizer.json").exists():
        ok("Tokenizer config exists")
    else:
        warn(f"Missing tokenizer_config.json or tokenizer.json in {model_dir}")
    safetensors = list(model_dir.glob("*.safetensors"))
    if safetensors:
        ok(f"Found {len(safetensors)} .safetensors file(s)")
    else:
        warn(f"No .safetensors files found in {model_dir}")


def ollama_tags(base_url: str) -> list[str] | None:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        warn(f"Ollama is not reachable at {base_url}: {exc}")
        return None
    models = data.get("models", [])
    return [str(item.get("name", "")) for item in models]


def check_ollama() -> None:
    if not check_file(OLLAMA_CONFIG, "Ollama model config"):
        return
    config = read_yaml(OLLAMA_CONFIG)
    base_url = config["runtime"]["base_url"]
    model_name = config["model"]["name"]
    names = ollama_tags(base_url)
    if names is None:
        return
    ok(f"Ollama API is reachable at {base_url}")
    if model_name in names:
        ok(f"Ollama model is available via API: {model_name}")
    else:
        warn(f"Ollama model {model_name!r} was not found via API. Available models: {names}")

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, check=False)
    except FileNotFoundError:
        warn("'ollama list' could not run because the ollama executable is not on PATH.")
        return
    except PermissionError as exc:
        warn(f"'ollama list' could not run because access was denied: {exc}")
        return
    except subprocess.SubprocessError as exc:
        warn(f"'ollama list' could not run: {exc}")
        return
    if result.returncode != 0:
        warn(f"'ollama list' failed: {result.stderr.strip()}")
        return
    if model_name in result.stdout:
        ok(f"Ollama model is listed by 'ollama list': {model_name}")
    else:
        warn(f"Ollama model {model_name!r} was not found in 'ollama list'.")


def main() -> None:
    print("Model setup check")
    check_hf_model()
    check_ollama()


if __name__ == "__main__":
    main()
