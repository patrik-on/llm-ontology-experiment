from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import read_yaml
from llm_ontology.evaluation.prediction_io import pick_first, read_jsonl, write_jsonl


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


def merged_inference_config(global_config: dict[str, Any], model_config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    config = dict(global_config.get("inference", {}))
    config.update(model_config.get("inference", {}))
    if args.device != "auto":
        config["device_map"] = args.device
    if args.offload_dir:
        config["offload_dir"] = args.offload_dir
    if args.load_in_4bit is not None:
        config["load_in_4bit"] = args.load_in_4bit
    config.setdefault("device_map", "auto")
    config.setdefault("torch_dtype", "float16")
    config.setdefault("load_in_4bit", False)
    return config


def peft_from_pretrained_with_fallback(base_model: Any, adapter_path: str, device_map: str | None, offload_dir: str | None):
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


def load_eval_model(model_config: dict[str, Any], inference_config: dict[str, Any]):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(model_config["model_path"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    device_map = inference_config.get("device_map", "auto")
    offload_dir = inference_config.get("offload_dir")
    if offload_dir:
        Path(offload_dir).mkdir(parents=True, exist_ok=True)

    dtype = torch_dtype_from_name(torch, inference_config.get("torch_dtype"))
    kwargs: dict[str, Any] = {
        "trust_remote_code": True,
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
            bnb_4bit_compute_dtype=torch_dtype_from_name(torch, inference_config.get("bnb_4bit_compute_dtype", "float16")),
            bnb_4bit_use_double_quant=bool(inference_config.get("bnb_4bit_use_double_quant", True)),
            bnb_4bit_quant_type=str(inference_config.get("bnb_4bit_quant_type", "nf4")),
        )

    model = AutoModelForCausalLM.from_pretrained(model_config["model_path"], **kwargs)
    if model_config.get("adapter_path"):
        model = peft_from_pretrained_with_fallback(
            model,
            model_config["adapter_path"],
            str(device_map) if device_map else None,
            str(offload_dir) if offload_dir else None,
        )
    model.eval()
    return model, tokenizer


def messages_for_task(task: str, input_code: str) -> list[dict[str, str]]:
    if task == "testing":
        return [
            {
                "role": "system",
                "content": "You are a Java developer specialized in writing concise and correct JUnit tests.",
            },
            {
                "role": "user",
                "content": (
                    "Generate a JUnit test for the following Java method. Return only Java test code, "
                    "without explanations.\n\nJava method:\n```java\n"
                    f"{input_code}\n```"
                ),
            },
        ]
    return [
        {
            "role": "system",
            "content": "You are a Java refactoring assistant. Preserve behavior and return only refactored Java code.",
        },
        {
            "role": "user",
            "content": (
                "Refactor the following Java code. Return only the refactored Java code, without explanations.\n\n"
                "Original Java code:\n```java\n"
                f"{input_code}\n```"
            ),
        },
    ]


def fallback_prompt_for_task(task: str, input_code: str) -> str:
    if task == "testing":
        return (
            "Generate a JUnit test for the following Java method. Return only Java test code.\n\n"
            f"Java method:\n{input_code}\n\nJUnit test:\n"
        )
    return (
        "Refactor the following Java code. Return only refactored Java code.\n\n"
        f"Original Java code:\n{input_code}\n\nRefactored Java code:\n"
    )


def as_input_ids(encoded: Any) -> Any:
    if hasattr(encoded, "shape"):
        return encoded
    if isinstance(encoded, dict) or hasattr(encoded, "__getitem__"):
        return encoded["input_ids"]
    return encoded


def encode_prompt(tokenizer: Any, task: str, input_code: str) -> tuple[Any, Any, str, list[dict[str, str]] | None]:
    messages = messages_for_task(task, input_code)
    if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
        input_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = as_input_ids(input_ids)
        return ids, ids.new_ones(ids.shape), str(rendered), messages
    prompt = fallback_prompt_for_task(task, input_code)
    encoded = tokenizer(prompt, return_tensors="pt")
    ids = as_input_ids(encoded)
    return ids, encoded.get("attention_mask", ids.new_ones(ids.shape)), prompt, None


def generate_prediction(
    model: Any,
    tokenizer: Any,
    task: str,
    input_code: str,
    generation: dict[str, Any],
    debug: bool = False,
    model_name: str = "",
    index: int = 0,
) -> tuple[str, dict[str, Any]]:
    input_ids, attention_mask, rendered_prompt, messages = encode_prompt(tokenizer, task, input_code)
    if hasattr(model, "device"):
        input_ids = input_ids.to(model.device)
        attention_mask = attention_mask.to(model.device)
    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    generate_kwargs = {
        "max_new_tokens": int(generation.get("max_new_tokens", 1024 if task == "refactoring" else 512)),
        "do_sample": bool(generation.get("do_sample", False)),
        "top_p": float(generation.get("top_p", 1.0)),
        "pad_token_id": pad_token_id,
        "repetition_penalty": float(generation.get("repetition_penalty", 1.05)),
    }
    if generate_kwargs["do_sample"]:
        generate_kwargs["temperature"] = float(generation.get("temperature", 0.0))
    output_ids = model.generate(input_ids=input_ids, attention_mask=attention_mask, **generate_kwargs)
    new_tokens = output_ids[0][input_ids.shape[-1] :]
    raw_generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    if debug and index == 0:
        print("\n=== DEBUG PROMPT ===")
        print(f"task: {task}")
        print(f"model_name: {model_name}")
        print(f"messages: {json.dumps(messages, ensure_ascii=False, indent=2) if messages else None}")
        print(f"prompt:\n{rendered_prompt}")
        print(f"input token length: {input_ids.shape[-1]}")
        print(f"raw decoded generated text:\n{raw_generated_text}")
        print(f"final extracted prediction:\n{prediction}")
        print("=== END DEBUG PROMPT ===\n")
    return prediction, generate_kwargs


def build_prediction_record(raw: dict[str, Any], task: str, model_name: str, index: int, prediction: str, generation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pick_first(raw, ("id", "sample_id", "refactoring_id"), f"{task}:{index}"),
        "task": task,
        "model_name": model_name,
        "source": raw.get("source", ""),
        "domain": raw.get("domain", task),
        "input": pick_first(raw, ("input", "prompt", "code_before")),
        "expected_output": pick_first(raw, ("output", "expected_output", "code_after", "reference_output")),
        "prediction": prediction,
        "metadata": {key: value for key, value in raw.items() if key not in {"instruction", "input", "output"}},
        "generation_config": generation,
    }


def run_inference(args: argparse.Namespace) -> None:
    models_config = read_yaml(args.models_config)
    generation = dict(models_config.get("generation", {}))
    if args.max_new_tokens is not None:
        generation["max_new_tokens"] = args.max_new_tokens
    elif args.task == "refactoring":
        generation["max_new_tokens"] = int(generation.get("refactoring_max_new_tokens", 1024))
    else:
        generation["max_new_tokens"] = int(generation.get("testing_max_new_tokens", generation.get("max_new_tokens", 512)))
    generation.setdefault("temperature", 0.0)
    generation.setdefault("do_sample", False)
    generation.setdefault("top_p", 1.0)
    generation.setdefault("repetition_penalty", 1.05)
    records = read_jsonl(args.dataset)
    if args.limit is not None:
        records = records[: args.limit]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for model_config in selected_models(models_config, args.model_name):
        output_path = output_dir / f"{model_config['name']}.jsonl"
        if output_path.exists() and not args.overwrite:
            print(f"Skipping existing predictions: {output_path}")
            continue
        inference_config = merged_inference_config(models_config, model_config, args)
        print(
            "Loading model "
            f"{model_config['name']} | adapter_path={model_config.get('adapter_path') or 'baseline'} "
            f"| device_map={inference_config.get('device_map')} "
            f"| load_in_4bit={bool(inference_config.get('load_in_4bit'))} "
            f"| offload_dir={inference_config.get('offload_dir')} "
            f"| max_new_tokens={generation.get('max_new_tokens')}"
        )
        model, tokenizer = load_eval_model(model_config, inference_config)
        predictions = []
        for index, raw in enumerate(records):
            input_text = pick_first(raw, ("input", "prompt", "code_before"))
            prediction, actual_generation = generate_prediction(
                model,
                tokenizer,
                args.task,
                input_text,
                generation,
                debug=args.debug_prompts,
                model_name=model_config["name"],
                index=index,
            )
            predictions.append(build_prediction_record(raw, args.task, model_config["name"], index, prediction, actual_generation))
        write_jsonl(predictions, output_path)
        print(f"Wrote predictions: {output_path}")
        try:
            import torch

            del model
            del tokenizer
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception as exc:
            print(f"[WARN] Cleanup after model inference failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation inference for baseline or LoRA models.")
    parser.add_argument("--task", required=True, choices=("testing", "refactoring"))
    parser.add_argument("--models-config", default="configs/evaluation/eval_models.yaml")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    parser.add_argument("--debug-prompts", action="store_true")
    parser.add_argument("--offload-dir", default=None)
    parser.add_argument("--load-in-4bit", dest="load_in_4bit", action="store_true", default=None)
    parser.add_argument("--no-load-in-4bit", dest="load_in_4bit", action="store_false")
    run_inference(parser.parse_args())


if __name__ == "__main__":
    main()
