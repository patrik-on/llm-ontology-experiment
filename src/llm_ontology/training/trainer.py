from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_ontology.core.paths import ensure_output_dirs, resolve_path
from llm_ontology.models.adapters import apply_lora
from llm_ontology.models.base_model import load_base_model, load_tokenizer
from llm_ontology.training.callbacks import build_callbacks
from llm_ontology.training.dataset import load_instruction_dataset, tokenize_records


def train_from_config(config: dict) -> Path:
    try:
        from datasets import Dataset
        from transformers import DataCollatorForLanguageModeling, Trainer, TrainingArguments
    except ImportError as exc:
        raise ImportError("Training requires optional ML dependencies: pip install -e .[training]") from exc

    ensure_output_dirs(config)
    train_records = load_instruction_dataset(resolve_path(config["data"]["train_file"]))
    val_records = load_instruction_dataset(resolve_path(config["data"]["val_file"]))

    tokenizer = load_tokenizer(config)
    model = apply_lora(load_base_model(config), config)
    max_length = int(config["model"]["max_seq_length"])

    train_dataset = Dataset.from_dict(tokenize_records(train_records, tokenizer, max_length))
    val_dataset = Dataset.from_dict(tokenize_records(val_records, tokenizer, max_length))

    training_config = config["training"]
    checkpoint_dir = resolve_path(config["output"]["checkpoint_dir"])
    args = TrainingArguments(
        output_dir=str(checkpoint_dir),
        num_train_epochs=training_config["epochs"],
        per_device_train_batch_size=training_config["batch_size"],
        gradient_accumulation_steps=training_config["gradient_accumulation_steps"],
        learning_rate=training_config["learning_rate"],
        warmup_ratio=training_config["warmup_ratio"],
        lr_scheduler_type=training_config["scheduler"],
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
        callbacks=build_callbacks(config),
    )
    trainer.train()
    adapter_dir = resolve_path(config["output"]["adapter_dir"])
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    return adapter_dir


def dry_run_training(config: dict) -> dict[str, Any]:
    ensure_output_dirs(config)
    return {
        "experiment": config["experiment"]["name"],
        "train_file": str(resolve_path(config["data"]["train_file"])),
        "adapter_dir": str(resolve_path(config["output"]["adapter_dir"])),
    }
