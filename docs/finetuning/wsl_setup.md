# WSL Fine-Tuning Setup

Tento dokument popisuje WSL2/Ubuntu setup pre QLoRA fine-tuning modelu Qwen2.5-Coder-7B-Instruct.

## Dôležité kompatibilitné poznámky

- Vo WSL používame `*_wsl.yaml` configy.
- Model path vo WSL je `/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct`.
- `Trainer` používa `processing_class=tokenizer`.
- `DataCollatorForSeq2Seq` používa `tokenizer=tokenizer` a `label_pad_token_id=-100`, aby ostal zachovaný loss mask iba na odpovedi.
- Natívny Windows nie je odporúčaný pre QLoRA, pretože `bitsandbytes` nemusí fungovať.

## Kontrola kompatibility

```bash
cd /path/to/llm-ontology-experiment
source .venv_wsl/bin/activate

python -m llm_ontology.env check
```

## Experiment outputs

WSL fine-tuning outputs are stored outside the OneDrive-backed repository to avoid checkpoint stalls caused by `/mnt/c` filesystem and OneDrive synchronization.

Output root:

```text
~/experiments/llm-ontology-v3
```

The repository remains on `/mnt/c`, but checkpoints, logs, results and final adapters are written to the native WSL filesystem.

## Tréning v3 adaptérov

Štyri adaptéry (`b2_testing`, `b2_refactoring`, `b2_testing_onto`, `b2_refactoring_onto`) a
ich poradie sú v `docs/finetuning/v3_runbook.md`. Pred každým behom:

```bash
python scripts/finetuning/check_finetuning_ready.py --config configs/finetuning/training_b2_testing_wsl.yaml
```

## Pokračovanie po prerušení

Checkpoint sa ukladá každých 100 krokov. Beh zastav `kill -TERM` (nie Ctrl+C, ten uloží
`final_adapter` ako interrupted), prázdny `final_adapter` zmaž a pokračuj:

```bash
python scripts/finetuning/train_finetuning.py \
  --config configs/finetuning/training_b2_refactoring_onto_wsl.yaml \
  --resume_from_checkpoint ~/experiments/llm-ontology-v3/b2_refactoring_onto/checkpoints/checkpoint-700
```

Nepoužívaj `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`; WSL ho nepodporuje.
