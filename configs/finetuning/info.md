# configs/finetuning

LoRA/QLoRA tréningové konfigurácie (WSL + CUDA), aktuálne pre eval-aligned **v3** adaptéry:

- `lora_config.yaml`: LoRA, NF4 kvantizácia a training defaults,
- `training_b2_testing_wsl.yaml`: testing-only adaptér `b2_testing_v3`,
- `training_b2_refactoring_wsl.yaml`: refactoring-only adaptér `b2_refactoring_v3`,
- `training_b1_shared_wsl.yaml`: spoločný adaptér `b1_shared_v3`.

Všetky používajú `configs/shared/models/qwen25_coder_7b_hf_wsl.yaml` (`max_seq_length` 8192)
a dáta z `data/processed/v3/` (`scripts/datasets/prepare_v3_eval_aligned.py`). Výstupy idú
mimo repozitára. Postup: `docs/finetuning/v3_runbook.md`. v2 adaptéry (`training` na
`data/processed/{testing,refactoring,combined}`, 2048 tokenov) sú v Git histórii a v ich
`results/config_snapshot.yaml`.
