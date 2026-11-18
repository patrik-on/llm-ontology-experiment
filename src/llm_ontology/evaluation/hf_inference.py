"Local HF/PEFT loading and prediction primitives; matrices own evaluation and dispatch."

from __future__ import annotations

from pathlib import Path

from typing import Any

from llm_ontology.finetuning.prompt_formatter import format_inference_prompt


def selected_models(config: dict[str, Any], model_name: str | None) -> list[dict[str, Any]]:
    models = list(config.get("models", []))
    if model_name:
        models = [model for model in models if model["name"] == model_name]
        if not models:
            raise ValueError(f"Model not found in config: {model_name}")
    return models


def torch_dtype_from_name(torch: Any, dtype_name: str | None) -> Any:
    if not dtype_name:
        return None
    dtype = getattr(torch, str(dtype_name), None)
    if dtype is None:
        raise ValueError(f"Unsupported torch dtype: {dtype_name}")
    return dtype


def peft_from_pretrained_with_fallback(
    base_model: Any, adapter_path: str, device_map: str | None, offload_dir: str | None
):
    from peft import PeftModel

    attempts = [
        {"device_map": device_map, "offload_folder": offload_dir},
        {"offload_folder": offload_dir},
        {},
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        try:
            return PeftModel.from_pretrained(base_model, adapter_path, **clean_kwargs)
        except TypeError as exc:
            last_error = exc
            continue
        except ValueError as exc:
            last_error = exc
            if "offload" not in str(exc).lower():
                raise
            continue
    raise RuntimeError(
        "Failed to load PEFT adapter. If the model is dispatched with device_map='auto', "
        "ensure inference.offload_dir exists on native WSL storage and retry."
    ) from last_error


def is_lora_model(model_config: dict[str, Any]) -> bool:
    adapter_path = model_config.get("adapter_path")
    adapter_text = str(adapter_path).strip().lower() if adapter_path is not None else ""
    has_adapter_path = bool(adapter_text and adapter_text not in {"baseline", "none", "null"})
    return str(model_config.get("type", "")).lower() == "lora" or has_adapter_path


def load_eval_model(model_config: dict[str, Any], inference_config: dict[str, Any]):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    model_path = str(Path(model_config["model_path"]).expanduser())
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=bool(inference_config.get("trust_remote_code", True)),
        local_files_only=bool(inference_config.get("local_files_only", False)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    device_map = inference_config.get("device_map", "auto")
    offload_dir = inference_config.get("offload_dir")
    if offload_dir:
        offload_dir = str(Path(offload_dir).expanduser())
    if offload_dir:
        Path(offload_dir).mkdir(parents=True, exist_ok=True)

    dtype = torch_dtype_from_name(torch, inference_config.get("torch_dtype"))
    kwargs: dict[str, Any] = {
        "trust_remote_code": bool(inference_config.get("trust_remote_code", True)),
        "local_files_only": bool(inference_config.get("local_files_only", False)),
        "low_cpu_mem_usage": True,
        "device_map": device_map,
    }
    if dtype is not None:
        kwargs["torch_dtype"] = dtype
    if offload_dir:
        kwargs["offload_folder"] = offload_dir
    if bool(inference_config.get("load_in_4bit", False)):
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch_dtype_from_name(
                torch, inference_config.get("bnb_4bit_compute_dtype", "float16")
            ),
            bnb_4bit_use_double_quant=bool(inference_config.get("bnb_4bit_use_double_quant", True)),
            bnb_4bit_quant_type=str(inference_config.get("bnb_4bit_quant_type", "nf4")),
        )

    model = AutoModelForCausalLM.from_pretrained(model_path, **kwargs)
    if is_lora_model(model_config):
        model = peft_from_pretrained_with_fallback(
            model,
            str(Path(model_config["adapter_path"]).expanduser()),
            str(device_map) if device_map else None,
            str(offload_dir) if offload_dir else None,
        )
    model.eval()
    return model, tokenizer


def as_input_ids(encoded: Any) -> Any:
    if hasattr(encoded, "shape"):
        return encoded
    if isinstance(encoded, dict) or hasattr(encoded, "__getitem__"):
        return encoded["input_ids"]
    return encoded


def encode_prompt(tokenizer: Any, instruction: str, input_code: str) -> tuple[Any, Any, str]:
    prompt = format_inference_prompt(instruction, input_code)
    encoded = tokenizer(prompt, return_tensors="pt")
    ids = as_input_ids(encoded)
    return ids, encoded.get("attention_mask", ids.new_ones(ids.shape)), prompt


def generate_prediction(
    model: Any,
    tokenizer: Any,
    task: str,
    instruction: str,
    input_code: str,
    generation: dict[str, Any],
    debug: bool = False,
    model_name: str = "",
    index: int = 0,
    on_prompt: Any = None,
) -> tuple[str, dict[str, Any]]:
    input_ids, attention_mask, rendered_prompt = encode_prompt(tokenizer, instruction, input_code)
    if on_prompt is not None:
        # The exact string that was tokenized, handed over just before generation
        # (the matrices compare it byte for byte with the frozen prompt and charge it).
        on_prompt(rendered_prompt)
    if hasattr(model, "device"):
        input_ids = input_ids.to(model.device)
        attention_mask = attention_mask.to(model.device)
    pad_token_id = (
        tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    )
    generate_kwargs = {
        "max_new_tokens": int(
            generation.get("max_new_tokens", 1024 if task == "refactoring" else 512)
        ),
        "do_sample": bool(generation.get("do_sample", False)),
        "top_p": float(generation.get("top_p", 1.0)),
        "pad_token_id": pad_token_id,
        "repetition_penalty": float(generation.get("repetition_penalty", 1.05)),
    }
    if generate_kwargs["do_sample"]:
        generate_kwargs["temperature"] = float(generation.get("temperature", 0.0))
    output_ids = model.generate(
        input_ids=input_ids, attention_mask=attention_mask, **generate_kwargs
    )
    new_tokens = output_ids[0][input_ids.shape[-1] :]
    raw_generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    if debug and index == 0:
        print("\n=== DEBUG PROMPT ===")
        print(f"task: {task}")
        print(f"model_name: {model_name}")
        print(f"prompt:\n{rendered_prompt}")
        print(f"input token length: {input_ids.shape[-1]}")
        print(f"raw decoded generated text:\n{raw_generated_text}")
        print(f"final extracted prediction:\n{prediction}")
        print("=== END DEBUG PROMPT ===\n")
    # Observed metadata, not additional generate() arguments. Keep exact decoded continuation.
    count = int(new_tokens.shape[-1])
    eos_ids = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
    if eos_ids is None:
        eos_ids = tokenizer.eos_token_id
    eos_ids = eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids]
    ended_eos = bool(count and int(new_tokens[-1]) in eos_ids)
    finish = (
        "eos"
        if ended_eos
        else "length"
        if count >= generate_kwargs["max_new_tokens"]
        else "stopped_unknown"
    )
    return prediction, {
        **generate_kwargs,
        "input_tokens": int(input_ids.shape[-1]),
        "output_tokens": count,
        "finish_reason": finish,
        "output_truncated": finish == "length",
        "raw_response": tokenizer.decode(new_tokens, skip_special_tokens=True),
    }
