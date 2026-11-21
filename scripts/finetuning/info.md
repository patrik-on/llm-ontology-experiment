# scripts/finetuning

CLI nástroje pre LoRA/QLoRA fine-tuning vo WSL s CUDA.

- `check_finetuning_ready.py`: model, dáta, configy a output paths (read-only),
- `train_finetuning.py`: hlavný training entrypoint (`--resume_from_checkpoint`, `--dry-run`, `--max_steps`),
- `debug_prompt_masking.py`: EOS, truncation a `labels=-100`,
- `diagnose_token_lengths.py`: dĺžky tokenizovaných záznamov.

Bezpečný smoke run:

```bash
python scripts/finetuning/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --dry-run \
  --max_steps 2 \
  --max_train_samples 4 \
  --max_val_samples 2 \
  --output-root /tmp/llm-ontology-dry-run
```

Postup v3 tréningu: `docs/finetuning/v3_runbook.md`.
