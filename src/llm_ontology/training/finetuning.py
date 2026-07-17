from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_ontology.core.config import read_yaml
from llm_ontology.finetuning.dataset_loader import load_instruction_dataset
from llm_ontology.finetuning.model_loader import apply_lora, load_base_model, load_tokenizer
from llm_ontology.finetuning.prompt_formatter import format_prompt, format_training_prompt


def ensure_output_dirs(output_config: dict[str, Any]) -> None:
    for key in ("output_dir", "logging_dir", "results_dir", "final_adapter_dir"):
        Path(output_config[key]).mkdir(parents=True, exist_ok=True)


def setup_file_logger(logging_dir: str | Path, experiment_name: str) -> logging.Logger:
    log_path = Path(logging_dir) / "training.log"
    logger = logging.getLogger(f"finetuning.{experiment_name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_config_snapshot(path: str | Path, training_config: dict, model_config: dict, lora_config: dict) -> None:
    payload = {
        "training_config": training_config,
        "model_config": model_config,
        "lora_config": lora_config,
    }
    try:
        import yaml

        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    except ImportError:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8")


def summary_path(results_dir: str | Path) -> Path:
    return Path(results_dir) / "training_summary.json"


def build_summary_base(
    training_config: dict,
    model_config: dict,
    lora_config: dict,
    train_examples: int = 0,
    val_examples: int = 0,
    resume_from_checkpoint: str | None = None,
) -> dict[str, Any]:
    defaults = lora_config["training_defaults"]
    lora = lora_config["lora"]
    run = training_config["run"]
    return {
        "experiment": training_config["experiment"]["name"],
        "status": "running",
        "started_at": now_iso(),
        "base_model": model_config["model"]["name"],
        "train_file": training_config["dataset"]["train_file"],
        "val_file": training_config["dataset"]["val_file"],
        "train_examples": train_examples,
        "val_examples": val_examples,
        "planned_epochs": int(defaults["num_train_epochs"]),
        "planned_steps": int(run["max_steps"]) if run.get("max_steps") is not None else None,
        "learning_rate": float(defaults["learning_rate"]),
        "lora_r": int(lora["r"]),
        "lora_alpha": int(lora["alpha"]),
        "final_adapter_dir": training_config["output"]["final_adapter_dir"],
        "early_stopping_enabled": int(defaults.get("early_stopping_patience") or 0) > 0,
        "early_stopping_patience": defaults.get("early_stopping_patience"),
        "load_best_model_at_end": bool(defaults.get("load_best_model_at_end", False)),
        "metric_for_best_model": defaults.get("metric_for_best_model"),
        "resumed_from_checkpoint": resume_from_checkpoint,
    }


def write_summary(results_dir: str | Path, payload: dict[str, Any]) -> None:
    write_json(summary_path(results_dir), payload)


def latest_metric_from_history(trainer: Any, key: str) -> float | None:
    history = getattr(getattr(trainer, "state", None), "log_history", []) or []
    for item in reversed(history):
        if key in item and item[key] is not None:
            return float(item[key])
    return None


def get_latest_eval_loss(trainer: Any) -> float | None:
    return latest_metric_from_history(trainer, "eval_loss")


def get_best_eval_loss(trainer: Any) -> float | None:
    state = getattr(trainer, "state", None)
    best_metric = getattr(state, "best_metric", None)
    if best_metric is not None:
        return float(best_metric)
    history = getattr(state, "log_history", []) or []
    values = [float(item["eval_loss"]) for item in history if item.get("eval_loss") is not None]
    return min(values) if values else None


def get_latest_train_loss(trainer: Any) -> float | None:
    return latest_metric_from_history(trainer, "loss")


def get_best_model_checkpoint(trainer: Any) -> str | None:
    checkpoint = getattr(getattr(trainer, "state", None), "best_model_checkpoint", None)
    return str(checkpoint) if checkpoint else None


def get_best_metric(trainer: Any) -> float | None:
    metric = getattr(getattr(trainer, "state", None), "best_metric", None)
    return float(metric) if metric is not None else None


def completed_steps(trainer: Any | None) -> int | None:
    if trainer is None:
        return None
    step = getattr(getattr(trainer, "state", None), "global_step", None)
    return int(step) if step is not None else None


def completed_epochs(trainer: Any | None) -> float | None:
    if trainer is None:
        return None
    epoch = getattr(getattr(trainer, "state", None), "epoch", None)
    return float(epoch) if epoch is not None else None


def validate_final_adapter(final_adapter_dir: Path, logger: logging.Logger) -> bool:
    required = (final_adapter_dir / "adapter_config.json", final_adapter_dir / "adapter_model.safetensors")
    valid = all(path.exists() for path in required)
    if not valid:
        logger.warning("Final adapter validation failed. Expected files: %s", ", ".join(str(path) for path in required))
    return valid


def latest_checkpoint(output_dir: str | Path) -> Path | None:
    root = Path(output_dir)
    checkpoints: list[tuple[int, Path]] = []
    for path in root.glob("checkpoint-*"):
        if not path.is_dir():
            continue
        try:
            number = int(path.name.split("-", 1)[1])
        except (IndexError, ValueError):
            continue
        checkpoints.append((number, path))
    if not checkpoints:
        return None
    return max(checkpoints, key=lambda item: item[0])[1]


def copy_latest_checkpoint_to_final_adapter(output_dir: str | Path, final_adapter_dir: Path, logger: logging.Logger) -> bool:
    checkpoint = latest_checkpoint(output_dir)
    if checkpoint is None:
        logger.warning("No checkpoint-* directory found in %s", output_dir)
        return False
    logger.warning("Copying latest checkpoint to final adapter: %s -> %s", checkpoint, final_adapter_dir)
    if final_adapter_dir.exists():
        shutil.rmtree(final_adapter_dir)
    shutil.copytree(checkpoint, final_adapter_dir)
    return True


def save_final_adapter(
    trainer: Any,
    tokenizer: Any,
    training_config: dict,
    logger: logging.Logger,
    allow_checkpoint_fallback: bool = False,
) -> bool:
    final_adapter_dir = Path(training_config["output"]["final_adapter_dir"])
    final_adapter_dir.mkdir(parents=True, exist_ok=True)
    try:
        trainer.save_model(final_adapter_dir)
        tokenizer.save_pretrained(final_adapter_dir)
    except Exception:
        logger.exception("trainer.save_model failed while saving final adapter")
        if not allow_checkpoint_fallback:
            raise
        try:
            copied = copy_latest_checkpoint_to_final_adapter(training_config["output"]["output_dir"], final_adapter_dir, logger)
            if copied:
                tokenizer.save_pretrained(final_adapter_dir)
        except Exception:
            logger.exception("Failed to copy latest checkpoint into final_adapter_dir")
    return validate_final_adapter(final_adapter_dir, logger)


def update_summary(
    base_summary: dict[str, Any],
    results_dir: str | Path,
    status: str,
    trainer: Any | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = dict(base_summary)
    payload["status"] = status
    payload["completed_steps"] = completed_steps(trainer)
    payload["completed_epochs"] = completed_epochs(trainer)
    payload["best_eval_loss"] = None
    payload["last_eval_loss"] = None
    payload["final_train_loss"] = None
    payload["final_adapter_valid"] = None
    if trainer is not None:
        payload["best_eval_loss"] = get_best_eval_loss(trainer)
        payload["last_eval_loss"] = get_latest_eval_loss(trainer)
        payload["final_train_loss"] = get_latest_train_loss(trainer)
        payload["best_model_checkpoint"] = get_best_model_checkpoint(trainer)
        payload["best_metric"] = get_best_metric(trainer)
    payload.update(extra)
    write_summary(results_dir, payload)
    return payload


def require_training_packages() -> None:
    missing = []
    for package_name in ("datasets", "transformers", "peft", "accelerate", "torch"):
        try:
            __import__(package_name)
        except ImportError:
            missing.append(package_name)
    if missing:
        raise ImportError(f"Missing fine-tuning dependencies: {', '.join(missing)}. Run: pip install -r requirements.txt")


def build_tokenized_training_example(record: dict[str, Any], tokenizer: Any, max_seq_length: int) -> dict[str, Any] | None:
    eos_token = getattr(tokenizer, "eos_token", None) or ""
    prompt = format_prompt(record)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    output_ids = tokenizer(f"{record['output']}{eos_token}", add_special_tokens=False)["input_ids"]
    if max_seq_length < 2 or not output_ids:
        return None

    if len(prompt_ids) + len(output_ids) > max_seq_length:
        output_budget = min(len(output_ids), max_seq_length - 1)
        prompt_budget = max_seq_length - output_budget
        prompt_ids = prompt_ids[-prompt_budget:]
        output_ids = output_ids[:output_budget]

    input_ids = list(prompt_ids) + list(output_ids)
    labels = [-100] * len(prompt_ids) + list(output_ids)
    if not any(label != -100 for label in labels):
        return None
    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


def make_hf_dataset(records: list[dict[str, Any]], tokenizer: Any, max_seq_length: int) -> Any:
    from datasets import Dataset

    features = [
        feature
        for record in records
        if (feature := build_tokenized_training_example(record, tokenizer, max_seq_length)) is not None
    ]
    if not features:
        raise ValueError("No training examples retained any output tokens after truncation.")
    return Dataset.from_list(features)


def training_arguments_kwargs(defaults: dict[str, Any], training_config: dict[str, Any]) -> dict[str, Any]:
    run = training_config["run"]
    kwargs: dict[str, Any] = {
        "output_dir": training_config["output"]["output_dir"],
        "logging_dir": training_config["output"]["logging_dir"],
        "learning_rate": float(defaults["learning_rate"]),
        "num_train_epochs": int(defaults["num_train_epochs"]),
        "per_device_train_batch_size": int(defaults["per_device_train_batch_size"]),
        "per_device_eval_batch_size": int(defaults["per_device_eval_batch_size"]),
        "gradient_accumulation_steps": int(defaults["gradient_accumulation_steps"]),
        "warmup_ratio": float(defaults["warmup_ratio"]),
        "weight_decay": float(defaults["weight_decay"]),
        "logging_steps": int(defaults["logging_steps"]),
        "save_steps": int(defaults["save_steps"]),
        "eval_steps": int(defaults["eval_steps"]),
        "save_total_limit": int(defaults["save_total_limit"]),
        "fp16": bool(defaults.get("fp16", True)),
        "report_to": defaults.get("report_to", "none"),
        "save_strategy": "steps",
        "logging_strategy": "steps",
        "seed": int(run.get("seed", 42)),
        "remove_unused_columns": False,
    }
    for key in ("load_best_model_at_end", "metric_for_best_model", "greater_is_better"):
        if key in defaults:
            kwargs[key] = defaults[key]
    if run.get("max_steps") is not None:
        kwargs["max_steps"] = int(run["max_steps"])
    return kwargs


def apply_training_overrides(
    training_config: dict[str, Any],
    *,
    dry_run: bool = False,
    max_steps: int | None = None,
    max_train_samples: int | None = None,
    max_val_samples: int | None = None,
    seed: int | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    if dry_run:
        training_config.setdefault("run", {})["dry_run"] = True
    if max_steps is not None:
        training_config.setdefault("run", {})["max_steps"] = max_steps
    if max_train_samples is not None:
        training_config.setdefault("run", {})["max_train_samples"] = max_train_samples
    if max_val_samples is not None:
        training_config.setdefault("run", {})["max_val_samples"] = max_val_samples
    if seed is not None:
        training_config.setdefault("run", {})["seed"] = seed
    if output_root is not None:
        experiment_name = training_config["experiment"]["name"]
        output_base = Path(output_root)
        root = output_base if output_base.name == experiment_name else output_base / experiment_name
        training_config["output"] = {
            "output_dir": str(root / "checkpoints"),
            "logging_dir": str(root / "logs"),
            "results_dir": str(root / "results"),
            "final_adapter_dir": str(root / "checkpoints" / "final_adapter"),
        }
    return training_config


def apply_lora_training_overrides(lora_config: dict[str, Any], *, dry_run: bool = False, max_steps: int | None = None) -> dict[str, Any]:
    if dry_run and max_steps is not None:
        defaults = lora_config.setdefault("training_defaults", {})
        checkpoint_steps = max(1, int(max_steps))
        defaults["save_steps"] = checkpoint_steps
        defaults["eval_steps"] = checkpoint_steps
        defaults["logging_steps"] = 1
    return lora_config


def dataset_sample_limits(run_config: dict[str, Any]) -> tuple[int | None, int | None]:
    return run_config.get("max_train_samples"), run_config.get("max_val_samples")


def set_eval_strategy(kwargs: dict[str, Any]) -> dict[str, Any]:
    from transformers import TrainingArguments

    init_vars = TrainingArguments.__dataclass_fields__
    if "eval_strategy" in init_vars:
        kwargs["eval_strategy"] = "steps"
    else:
        kwargs["evaluation_strategy"] = "steps"
    return kwargs


def extract_losses(train_result: Any, eval_metrics: dict[str, Any]) -> tuple[float | None, float | None]:
    train_loss = None
    if hasattr(train_result, "training_loss"):
        train_loss = float(train_result.training_loss)
    eval_loss = eval_metrics.get("eval_loss")
    if eval_loss is not None:
        eval_loss = float(eval_loss)
    return train_loss, eval_loss


def run_training(
    config_path: str | Path,
    resume_from_checkpoint: str | None = None,
    *,
    dry_run: bool = False,
    max_steps: int | None = None,
    max_train_samples: int | None = None,
    max_val_samples: int | None = None,
    seed: int | None = None,
    output_root: str | Path | None = None,
) -> None:
    if resume_from_checkpoint and not Path(resume_from_checkpoint).exists():
        raise FileNotFoundError(f"Resume checkpoint does not exist: {resume_from_checkpoint}")

    training_config = apply_training_overrides(
        read_yaml(config_path),
        dry_run=dry_run,
        max_steps=max_steps,
        max_train_samples=max_train_samples,
        max_val_samples=max_val_samples,
        seed=seed,
        output_root=output_root,
    )
    model_config = read_yaml(training_config["experiment"]["model_config"])
    lora_config = apply_lora_training_overrides(read_yaml(training_config["experiment"]["lora_config"]), dry_run=dry_run, max_steps=max_steps)
    ensure_output_dirs(training_config["output"])

    logger = setup_file_logger(training_config["output"]["logging_dir"], training_config["experiment"]["name"])
    logger.info("Starting fine-tuning run at %s", datetime.now().isoformat(timespec="seconds"))
    logger.info("Experiment: %s", training_config["experiment"]["name"])
    logger.info("Model path: %s", model_config["model"]["name"])
    logger.info("Train file: %s", training_config["dataset"]["train_file"])
    logger.info("Val file: %s", training_config["dataset"]["val_file"])
    if resume_from_checkpoint:
        logger.info("Resuming training from checkpoint: %s", resume_from_checkpoint)

    snapshot_path = Path(training_config["output"]["results_dir"]) / "config_snapshot.yaml"
    write_config_snapshot(snapshot_path, training_config, model_config, lora_config)

    train_examples = 0
    val_examples = 0
    trainer = None
    tokenizer = None
    base_summary = build_summary_base(training_config, model_config, lora_config, resume_from_checkpoint=resume_from_checkpoint)
    try:
        require_training_packages()
        run = training_config["run"]
        dry_run = bool(run.get("dry_run", False))
        max_train_samples, max_val_samples = dataset_sample_limits(run)

        train_records, val_records = load_instruction_dataset(
            training_config["dataset"]["train_file"],
            training_config["dataset"]["val_file"],
            max_train_samples=max_train_samples,
            max_val_samples=max_val_samples,
        )
        train_examples = len(train_records)
        val_examples = len(val_records)
        base_summary = build_summary_base(
            training_config,
            model_config,
            lora_config,
            train_examples,
            val_examples,
            resume_from_checkpoint=resume_from_checkpoint,
        )
        write_summary(training_config["output"]["results_dir"], base_summary)
        logger.info("Train examples: %s", train_examples)
        logger.info("Val examples: %s", val_examples)
        logger.info("LoRA config: r=%s alpha=%s dropout=%s", lora_config["lora"]["r"], lora_config["lora"]["alpha"], lora_config["lora"]["dropout"])
        logger.info("Training defaults: %s", lora_config["training_defaults"])
        if model_config.get("runtime", {}).get("load_in_4bit") or lora_config.get("quantization", {}).get("load_in_4bit"):
            try:
                import bitsandbytes  # noqa: F401
            except ImportError as exc:
                raise ImportError(
                    "4-bit QLoRA is enabled, but bitsandbytes is not available. "
                    "Use WSL2/Linux with CUDA, or set load_in_4bit to false in the configs."
                ) from exc

        tokenizer = load_tokenizer(model_config)
        max_seq_length = int(model_config.get("runtime", {}).get("max_seq_length", 2048))
        tokenized_train = make_hf_dataset(train_records, tokenizer, max_seq_length)
        tokenized_val = make_hf_dataset(val_records, tokenizer, max_seq_length)

        model = load_base_model(model_config, lora_config.get("quantization"))
        model = apply_lora(model, lora_config)
        if hasattr(model, "print_trainable_parameters"):
            model.print_trainable_parameters()

        from transformers import DataCollatorForSeq2Seq, EarlyStoppingCallback, Trainer, TrainingArguments

        args_kwargs = set_eval_strategy(training_arguments_kwargs(lora_config["training_defaults"], training_config))
        training_args = TrainingArguments(**args_kwargs)
        collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model, label_pad_token_id=-100)
        callbacks = []
        early_stopping_patience = int(lora_config["training_defaults"].get("early_stopping_patience") or 0)
        if early_stopping_patience > 0:
            callbacks.append(EarlyStoppingCallback(early_stopping_patience=early_stopping_patience))
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_val,
            data_collator=collator,
            processing_class=tokenizer,
            callbacks=callbacks,
        )

        try:
            if resume_from_checkpoint:
                train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
            else:
                train_result = trainer.train()
        except KeyboardInterrupt:
            logger.warning("Fine-tuning was manually interrupted with Ctrl+C.")
            final_adapter_valid = save_final_adapter(
                trainer,
                tokenizer,
                training_config,
                logger,
                allow_checkpoint_fallback=True,
            )
            update_summary(
                base_summary,
                training_config["output"]["results_dir"],
                "interrupted",
                trainer=trainer,
                final_adapter_valid=final_adapter_valid,
                interrupted_at=now_iso(),
                best_model_checkpoint=get_best_model_checkpoint(trainer),
                best_metric=get_best_metric(trainer),
                note=(
                    "Training was manually interrupted; final_adapter was saved from current trainer state "
                    "or latest checkpoint."
                ),
            )
            logger.warning("Interrupted run summary saved.")
            raise SystemExit(130) from None
        eval_metrics = trainer.evaluate()
        final_adapter_dir = Path(training_config["output"]["final_adapter_dir"])
        final_adapter_valid = save_final_adapter(trainer, tokenizer, training_config, logger)
        final_train_loss, final_eval_loss = extract_losses(train_result, eval_metrics)
        update_summary(
            base_summary,
            training_config["output"]["results_dir"],
            "completed",
            trainer=trainer,
            final_train_loss=final_train_loss,
            best_eval_loss=get_best_eval_loss(trainer),
            last_eval_loss=get_latest_eval_loss(trainer) if get_latest_eval_loss(trainer) is not None else final_eval_loss,
            final_eval_loss=final_eval_loss,
            final_adapter_valid=final_adapter_valid,
            completed_at=now_iso(),
            best_model_checkpoint=get_best_model_checkpoint(trainer),
            best_metric=get_best_metric(trainer),
            note="Training completed; early stopping may have selected the best checkpoint based on eval_loss.",
        )
        logger.info("Training completed. Final adapter saved to %s", final_adapter_dir)
    except Exception as exc:
        logger.exception("Fine-tuning failed")
        update_summary(
            base_summary,
            training_config["output"]["results_dir"],
            "failed",
            trainer=trainer,
            error=str(exc),
            failed_at=now_iso(),
            final_adapter_valid=False,
        )
        raise
