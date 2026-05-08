# scripts/training

CLI skripty pre fine-tuning.

- `train_finetuning.py`: spustenie QLoRA/LoRA fine-tuningu,
- `check_finetuning_ready.py`: readiness check konkrétneho training configu,
- `check_transformers_compat.py`: kontrola PyTorch/Transformers/CUDA/bitsandbytes,
- `check_finetuning_setup.py`: staršia všeobecná kontrola setupu.

Hlavná logika je v `src/llm_ontology/training/`.
