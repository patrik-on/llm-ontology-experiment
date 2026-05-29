# V2 fine-tuning runbook

## Purpose

V2 modely sa trénujú po oprave prompt masking pipeline. Oproti v1/pilotným adaptérom používajú:

- jednotný prompt formatter pre tréning aj evaluáciu,
- datasetové `instruction` + `input`,
- EOS token na konci očakávaného výstupu,
- label masking prompt tokenov na `-100`,
- bezpečné truncation správanie, aby output labels neboli celé odrezané,
- `DataCollatorForSeq2Seq` s `label_pad_token_id=-100`.

Tento dokument pripravuje ručné spustenie tréningu. Reálny tréning spúšťa používateľ manuálne.

## Environment

Tréning spúšťaj vo WSL v koreňovom priečinku projektu:

```bash
cd /mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment
source .venv_wsl/bin/activate
```

## Pre-flight checks

Pred každým reálnym v2 tréningom spusti:

```bash
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/training/debug_prompt_masking.py
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
python scripts/check_finetuning_ready.py --config configs/finetuning/training_b1_shared_wsl.yaml
```

`check_finetuning_ready.py` validuje cesty uložené v YAML configoch. V2 output cesty sa pri ručnom tréningu presmerujú cez `--output-root`, aby sa neprepísali v1/pilotné adaptéry.

## Output root

V2 výstupy patria pod:

```text
/home/patrik/experiments/llm-ontology-v2
```

Očakávaná štruktúra:

```text
/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints
/home/patrik/experiments/llm-ontology-v2/b2_testing/logs
/home/patrik/experiments/llm-ontology-v2/b2_testing/results

/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints
/home/patrik/experiments/llm-ontology-v2/b2_refactoring/logs
/home/patrik/experiments/llm-ontology-v2/b2_refactoring/results

/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints
/home/patrik/experiments/llm-ontology-v2/b1_shared/logs
/home/patrik/experiments/llm-ontology-v2/b1_shared/results
```

## Training commands

Tieto príkazy sú pripravené na ručné spustenie. Nespúšťaj ich ako súčasť pre-flight kontroly.

### B2-T v2

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b2_testing
```

### B2-R v2

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b2_refactoring_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b2_refactoring
```

### B1 shared v2

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b1_shared_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b1_shared
```

## Resume commands

Nahraď `checkpoint-XXX` konkrétnym checkpointom, napríklad `checkpoint-300`.

### B2-T v2 resume

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b2_testing \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/checkpoint-XXX
```

### B2-R v2 resume

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b2_refactoring_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b2_refactoring \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/checkpoint-XXX
```

### B1 shared v2 resume

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b1_shared_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b1_shared \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/checkpoint-XXX
```

## Monitoring

Počas tréningu sleduj GPU:

```bash
watch -n 2 nvidia-smi
```

- GPU util by mal byť vysoký počas tréningových krokov.
- VRAM bude pri QLoRA behu pravdepodobne takmer plná.
- Ak GPU util ostáva dlhšie na `0 %`, skontroluj `logs/training.log` a terminálový výstup.

## After-run checks

Pre každý model skontroluj summary a final adapter.

### B2-T v2

```bash
cat /home/patrik/experiments/llm-ontology-v2/b2_testing/results/training_summary.json
ls /home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter
```

### B2-R v2

```bash
cat /home/patrik/experiments/llm-ontology-v2/b2_refactoring/results/training_summary.json
ls /home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter
```

### B1 shared v2

```bash
cat /home/patrik/experiments/llm-ontology-v2/b1_shared/results/training_summary.json
ls /home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter
```

Skontroluj:

- `status` je `completed` alebo pri ručnom prerušení `interrupted`,
- `final_adapter_valid: true`,
- `adapter_model.safetensors`,
- `adapter_config.json`.

## Notes

- V1/pilotné adaptéry neprepisovať:
  - `experiments/b2_testing/checkpoints/final_adapter`
  - `experiments/b2_refactoring/checkpoints/final_adapter`
  - `/home/patrik/experiments/llm-ontology/b1_shared/checkpoints/final_adapter`
- V2 adaptéry budú neskôr pridané do `configs/evaluation/eval_models.yaml` ako nové modely.
- Evaluation sa spustí až po dokončení v2 tréningu.
- Nemeň datasety ani LoRA/QLoRA hyperparametre počas prípravy v2 setupu.
