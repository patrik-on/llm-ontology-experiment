from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_ontology.core.config import read_yaml
from llm_ontology.finetuning.dataset_loader import load_jsonl, validate_example
from llm_ontology.finetuning.prompt_formatter import format_inference_prompt
from llm_ontology.inference.ollama_client import generate_with_ollama


def main() -> None:
    parser = argparse.ArgumentParser(description="Run limited Ollama baseline inference.")
    parser.add_argument("--config", default="configs/inference/ollama_qwen25_coder_baseline.yaml")
    args = parser.parse_args()

    config = read_yaml(args.config)
    model_config = read_yaml(config["model"]["config"])
    model_name = model_config["model"]["name"]
    runtime = model_config["runtime"]
    generation = config["generation"]
    limit = int(generation.get("limit_per_dataset", 20))

    output_path = Path(config["output"]["predictions_file"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for dataset_name, dataset_path in config["datasets"].items():
            records = load_jsonl(dataset_path)[:limit]
            for index, record in enumerate(records):
                if not validate_example(record):
                    raise ValueError(f"Invalid example in {dataset_path} at limited row {index + 1}.")
                prompt = format_inference_prompt(record["instruction"], record["input"])
                prediction = generate_with_ollama(
                    prompt=prompt,
                    model_name=model_name,
                    base_url=runtime["base_url"],
                    temperature=float(generation.get("temperature", runtime.get("temperature", 0.2))),
                    top_p=float(generation.get("top_p", runtime.get("top_p", 0.9))),
                    max_tokens=int(generation.get("max_tokens", runtime.get("max_tokens", 1024))),
                )
                payload = {
                    "id": f"{dataset_name}:{index}",
                    "domain": record.get("domain"),
                    "source": record.get("source"),
                    "instruction": record["instruction"],
                    "input": record["input"],
                    "reference_output": record["output"],
                    "prediction": prediction,
                    "model": model_name,
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                written += 1

    print(f"Wrote {written} predictions to {output_path}")


if __name__ == "__main__":
    main()
