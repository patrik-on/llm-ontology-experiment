# scripts/training

CLI skripty pre WSL/CUDA kontroly, prompt masking debug a LoRA/QLoRA fine-tuning.

Hlavná logika je v `src/llm_ontology/training/`, `src/llm_ontology/finetuning/` a v príslušných configoch pod `configs/finetuning/`.

## Skripty

- `check_transformers_compat.py`: najnižšia technická kontrola prostredia. Overí import `torch`, `transformers`, `bitsandbytes`, dostupnosť CUDA a kompatibilitu API pre `Trainer` a `DataCollatorForSeq2Seq`. Spúšťaj ho vo WSL pred riešením tréningových chýb.
- `check_finetuning_ready.py`: readiness check konkrétneho training configu. Overí model config, lokálny model, LoRA config, dataset súbory, output priečinky a či config nie je omylom nastavený ako malý dry-run. Pre WSL používaj `--config configs/finetuning/*_wsl.yaml`.
- `check_finetuning_setup.py`: staršia všeobecná kontrola nad Windows configmi. Je užitočná ako rýchla smoke kontrola prompt formattera a dataset súborov, ale pre reálny WSL tréning je presnejší `check_finetuning_ready.py`.
- `debug_prompt_masking.py`: malý predtréningový debug nástroj. Načíta niekoľko testing/refactoring príkladov vrátane najdlhšieho príkladu, tokenizuje prompt a odpoveď, vypíše počty prompt/full/output label tokenov, overí EOS token a skontroluje, že `DataCollatorForSeq2Seq` zachováva `labels=-100`.
- `train_finetuning.py`: hlavný CLI vstup pre LoRA/QLoRA tréning. Načíta YAML config, model, tokenizer, datasety, aplikuje LoRA, spustí `Trainer`, uloží checkpointy, `final_adapter` a `training_summary.json`.

## Bezpečný dry-run

Pred reálnym B1/B2 tréningom používaj izolovaný dry-run, ktorý neprepíše experimentálne výstupy:

```bash
python scripts/training/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --dry-run \
  --max_steps 2 \
  --max_train_samples 4 \
  --max_val_samples 2 \
  --output-root /tmp/llm-ontology-dry-run
```

`--output-root` presmeruje checkpointy, logy, výsledky aj `final_adapter` mimo reálneho experimentu. Pri `--dry-run --max_steps 2` sa nastaví aj krátke `save_steps/eval_steps`, aby vznikol test checkpoint.

## Reálny tréning

Reálne behy spúšťaj až po compile/test/debug kontrole:

```bash
python scripts/training/check_transformers_compat.py
python scripts/training/check_finetuning_ready.py --config configs/finetuning/training_b1_shared_wsl.yaml
python scripts/training/debug_prompt_masking.py
```

Potom spusti konkrétny experiment:

```bash
python scripts/training/train_finetuning.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/training/train_finetuning.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
python scripts/training/train_finetuning.py --config configs/finetuning/training_b1_shared_wsl.yaml
```

Na pokračovanie z checkpointu použi:

```bash
python scripts/training/train_finetuning.py \
  --config configs/finetuning/training_b1_shared_wsl.yaml \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology/b1_shared/checkpoints/checkpoint-300
```

Plný tréning nespúšťaj na natívnom Windows. QLoRA je určená pre CUDA-enabled WSL/Linux prostredie.
