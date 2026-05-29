from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.core.config import read_yaml
from llm_ontology.finetuning.dataset_loader import load_jsonl
from llm_ontology.finetuning.model_loader import load_tokenizer
from llm_ontology.finetuning.prompt_formatter import format_prompt, format_training_prompt
from llm_ontology.training.finetuning import build_tokenized_training_example


def selected_examples(records: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    examples = list(records[:count])
    longest = max(records, key=lambda item: len(str(item.get("input", ""))) + len(str(item.get("output", ""))))
    if longest not in examples:
        examples.append(longest)
    return examples


def debug_dataset(path: Path, tokenizer: Any, max_seq_length: int, count: int) -> list[dict[str, Any]]:
    records = load_jsonl(path)
    features: list[dict[str, Any]] = []
    print(f"\nDATASET {path}")
    for index, record in enumerate(selected_examples(records, count), 1):
        prompt = format_prompt(record)
        eos_token = getattr(tokenizer, "eos_token", None) or ""
        full_text = format_training_prompt(record, eos_token=eos_token)
        prompt_tokens = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        feature = build_tokenized_training_example(record, tokenizer, max_seq_length)
        if feature is None:
            raise RuntimeError(f"{path} example {index} lost all output labels after truncation.")

        labels = list(feature["labels"])
        unmasked_label_tokens = sum(1 for label in labels if label != -100)
        labels_start_masked = bool(labels) and labels[0] == -100
        any_output_unmasked = unmasked_label_tokens > 0
        text_ends_with_eos = full_text.endswith(eos_token) if eos_token else "no_eos_token"
        print(
            "example={index} source={source} domain={domain} "
            "prompt_tokens={prompt_tokens} full_input_tokens={full_input_tokens} "
            "unmasked_label_tokens={unmasked_label_tokens} labels_start_masked={labels_start_masked} "
            "any_output_unmasked={any_output_unmasked} text_ends_with_eos={text_ends_with_eos}".format(
                index=index,
                source=record.get("source", ""),
                domain=record.get("domain", ""),
                prompt_tokens=len(prompt_tokens),
                full_input_tokens=len(feature["input_ids"]),
                unmasked_label_tokens=unmasked_label_tokens,
                labels_start_masked=labels_start_masked,
                any_output_unmasked=any_output_unmasked,
                text_ends_with_eos=text_ends_with_eos,
            )
        )
        if not labels_start_masked:
            raise RuntimeError(f"{path} example {index} labels do not start with -100.")
        if not any_output_unmasked:
            raise RuntimeError(f"{path} example {index} has no unmasked output labels.")
        features.append(feature)
    return features


def check_collator_preserves_mask(tokenizer: Any, features: list[dict[str, Any]]) -> None:
    from transformers import DataCollatorForSeq2Seq

    collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, label_pad_token_id=-100)
    batch = collator(features[:2])
    labels = batch["labels"]
    if hasattr(labels, "detach"):
        labels_list = labels.detach().cpu().tolist()
    else:
        labels_list = labels
    if not any(label == -100 for row in labels_list for label in row):
        raise RuntimeError("DataCollatorForSeq2Seq did not preserve any -100 label masks.")
    print("\nDataCollatorForSeq2Seq preserved labels=-100 in the debug batch.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug prompt tokenization, EOS handling, and label masking.")
    parser.add_argument("--model-config", default="configs/models/qwen25_coder_7b_hf_wsl.yaml")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["data/processed/testing/train.jsonl", "data/processed/refactoring/train.jsonl"],
    )
    parser.add_argument("--examples", type=int, default=2)
    args = parser.parse_args()

    model_config = read_yaml(args.model_config)
    tokenizer = load_tokenizer(model_config)
    max_seq_length = int(model_config.get("runtime", {}).get("max_seq_length", 2048))
    print(f"tokenizer_eos_token={getattr(tokenizer, 'eos_token', None)!r}")
    print(f"max_seq_length={max_seq_length}")

    all_features: list[dict[str, Any]] = []
    for dataset in args.datasets:
        all_features.extend(debug_dataset(Path(dataset), tokenizer, max_seq_length, args.examples))
    check_collator_preserves_mask(tokenizer, all_features)
    print("\nPrompt masking debug check OK.")


if __name__ == "__main__":
    main()
