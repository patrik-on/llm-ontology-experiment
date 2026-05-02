from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_ontology.core.paths import ensure_dir, resolve_path
from llm_ontology.inference.prompts import build_prompt
from llm_ontology.models.adapters import load_adapter
from llm_ontology.models.base_model import load_base_model, load_tokenizer
from llm_ontology.training.dataset import load_instruction_dataset


def generate_text(model: Any, tokenizer: Any, prompt: str, max_new_tokens: int = 512) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(output_ids[0], skip_special_tokens=True).split("### Response:")[-1].strip()


def generate_predictions(config: dict) -> Path:
    test_records = load_instruction_dataset(resolve_path(config["data"]["test_file"]))
    result_dir = ensure_dir(resolve_path(config["output"]["result_dir"]))
    output_path = result_dir / "predictions.jsonl"

    tokenizer = load_tokenizer(config)
    model = load_adapter(load_base_model(config), str(resolve_path(config["output"]["adapter_dir"])))
    model.eval()

    with output_path.open("w", encoding="utf-8") as handle:
        for record in test_records:
            prediction = generate_text(model, tokenizer, build_prompt(record))
            payload = {
                "instruction": record["instruction"],
                "input": record["input"],
                "reference": record["output"],
                "prediction": prediction,
                "domain": record["domain"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return output_path
