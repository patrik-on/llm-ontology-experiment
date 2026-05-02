from __future__ import annotations

import importlib.util
from typing import Any


def _require_package(package_name: str) -> None:
    if importlib.util.find_spec(package_name) is None:
        raise ImportError(
            f"Missing optional dependency '{package_name}'. Install the fine-tuning dependencies before loading models."
        )


def _torch_dtype(dtype_name: str) -> Any:
    _require_package("torch")
    import torch

    dtype = getattr(torch, dtype_name, None)
    if dtype is None:
        raise ValueError(f"Unsupported torch dtype: {dtype_name}")
    return dtype


def load_tokenizer(model_config: dict) -> Any:
    _require_package("transformers")
    from transformers import AutoTokenizer

    model_section = model_config["model"]
    runtime = model_config.get("runtime", {})
    tokenizer_name = model_section.get("tokenizer_name") or model_section["name"]
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name,
        trust_remote_code=bool(runtime.get("trust_remote_code", True)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def load_base_model(model_config: dict) -> Any:
    _require_package("transformers")
    from transformers import AutoModelForCausalLM

    runtime = model_config.get("runtime", {})
    kwargs: dict[str, Any] = {
        "device_map": runtime.get("device_map", "auto"),
        "trust_remote_code": bool(runtime.get("trust_remote_code", True)),
    }
    if runtime.get("torch_dtype"):
        kwargs["torch_dtype"] = _torch_dtype(str(runtime["torch_dtype"]))
    if runtime.get("load_in_4bit"):
        if importlib.util.find_spec("bitsandbytes") is None:
            raise ImportError(
                "The config requests 4-bit loading, but bitsandbytes is not available. "
                "On Windows this is common; use a compatible Linux/CUDA environment or disable load_in_4bit."
            )
        kwargs["load_in_4bit"] = True
    return AutoModelForCausalLM.from_pretrained(model_config["model"]["name"], **kwargs)


def apply_lora(model: Any, lora_config: dict) -> Any:
    _require_package("peft")
    from peft import LoraConfig, get_peft_model

    lora = lora_config["lora"]
    config = LoraConfig(
        r=int(lora["r"]),
        lora_alpha=int(lora["alpha"]),
        lora_dropout=float(lora["dropout"]),
        bias=str(lora["bias"]),
        task_type=str(lora["task_type"]),
        target_modules=list(lora["target_modules"]),
    )
    return get_peft_model(model, config)
