# WSL Fine-Tuning Setup

Tento dokument popisuje WSL2/Ubuntu setup pre QLoRA fine-tuning modelu Qwen2.5-Coder-7B-Instruct.

## Dôležité kompatibilitné poznámky

- Vo WSL používame `*_wsl.yaml` configy.
- Model path vo WSL je `/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct`.
- `Trainer` používa `processing_class=tokenizer`.
- `DataCollatorForLanguageModeling` používa `tokenizer=tokenizer`.
- Natívny Windows nie je odporúčaný pre QLoRA, pretože `bitsandbytes` nemusí fungovať.

## Kontrola kompatibility

```bash
cd /mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment
source .venv_wsl/bin/activate

python scripts/check_transformers_compat.py
```

## Experiment outputs

WSL fine-tuning outputs are stored outside the OneDrive-backed repository to avoid checkpoint stalls caused by `/mnt/c` filesystem and OneDrive synchronization.

Output root:

```text
/home/patrik/experiments/llm-ontology
```

The repository remains on `/mnt/c`, but checkpoints, logs, results and final adapters are written to the native WSL filesystem.

## B2-T Testing

```bash
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/train_finetuning.py --config configs/finetuning/training_b2_testing_wsl.yaml
```

## B2-R Refactoring

```bash
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
python scripts/train_finetuning.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
```

## B1 Shared

```bash
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b1_shared_wsl.yaml
python scripts/train_finetuning.py --config configs/finetuning/training_b1_shared_wsl.yaml
```

## Resume interrupted training

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b1_shared_wsl.yaml \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology/b1_shared/checkpoints/checkpoint-300
```

Odporúčané poradie spustenia:

1. B2-T testing
2. B2-R refactoring
3. B1 shared
