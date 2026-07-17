# scripts/training

CLI nástroje pre WSL/CUDA kontrolu a LoRA/QLoRA fine-tuning.

- `check_transformers_compat.py`: CUDA a Transformers API kompatibilita,
- `check_finetuning_ready.py`: model, dáta, configy a output paths,
- `check_finetuning_setup.py`: staršia Windows smoke kontrola,
- `debug_prompt_masking.py`: EOS, truncation a `labels=-100`,
- `train_finetuning.py`: hlavný training entrypoint,
- `print_v2_training_commands.py`: reprodukovateľné v2 príkazy,
- `print_size_ablation_commands.py`: learning-curve command matrix.

Bezpečný smoke run:

```bash
python scripts/training/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --dry-run \
  --max_steps 2 \
  --max_train_samples 4 \
  --max_val_samples 2 \
  --output-root /tmp/llm-ontology-dry-run
```

Fine-tuning používaj vo WSL/Linux s CUDA. Modelové loadery sú centralizované v
`llm_ontology.models`; training pipeline sa neskôr môže kombinovať s RAG bez
nového tréningu.
