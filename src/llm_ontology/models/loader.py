from __future__ import annotations

from typing import Any


def load_tokenizer(config: dict[str, Any]) -> Any:
    """Load the configured tokenizer without importing training dependencies eagerly."""

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "Install the training extra to load tokenizers: pip install -e .[training]"
        ) from exc
    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["base_model"], use_fast=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def build_quantization_config(config: dict[str, Any]) -> Any | None:
    """Build the optional four-bit Transformers configuration."""

    quantization = config.get("quantization", {})
    if not quantization.get("load_in_4bit"):
        return None
    try:
        import torch
        from transformers import BitsAndBytesConfig
    except ImportError as exc:
        raise ImportError(
            "4-bit loading requires the training extra and bitsandbytes."
        ) from exc
    compute_dtype = getattr(
        torch, str(quantization.get("bnb_4bit_compute_dtype", "float16"))
    )
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=bool(
            quantization.get("bnb_4bit_use_double_quant", True)
        ),
        bnb_4bit_quant_type=str(quantization.get("bnb_4bit_quant_type", "nf4")),
    )


def load_base_model(config: dict[str, Any]) -> Any:
    """Load the configured causal LM and apply optional quantization settings."""

    try:
        from transformers import AutoModelForCausalLM
    except ImportError as exc:
        raise ImportError(
            "Install the training extra to load models: pip install -e .[training]"
        ) from exc
    model_kwargs: dict[str, Any] = {}
    quantization_config = build_quantization_config(config)
    if quantization_config is not None:
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["device_map"] = "auto"
    return AutoModelForCausalLM.from_pretrained(
        config["model"]["base_model"], **model_kwargs
    )


def apply_lora(model: Any, config: dict[str, Any]) -> Any:
    """Apply the repository LoRA settings to an already loaded base model."""

    try:
        from peft import (
            LoraConfig,
            TaskType,
            get_peft_model,
            prepare_model_for_kbit_training,
        )
    except ImportError as exc:
        raise ImportError("LoRA support requires peft: pip install -e .[training]") from exc
    if config.get("quantization", {}).get("load_in_4bit"):
        model = prepare_model_for_kbit_training(model)
    lora = config["lora"]
    peft_config = LoraConfig(
        r=lora["r"],
        lora_alpha=lora["alpha"],
        lora_dropout=lora["dropout"],
        target_modules=lora["target_modules"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    return get_peft_model(model, peft_config)


__all__ = [
    "apply_lora",
    "build_quantization_config",
    "load_base_model",
    "load_tokenizer",
]
