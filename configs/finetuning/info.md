# configs/finetuning

LoRA/QLoRA tréningové konfigurácie, ktorými vznikli v2 adaptéry (WSL + CUDA):

- `lora_config.yaml`: LoRA, NF4 kvantizácia a training defaults,
- `training_b2_testing_wsl.yaml`: testing-only adaptér `b2_testing_v2`,
- `training_b2_refactoring_wsl.yaml`: refactoring-only adaptér `b2_refactoring_v2`,
- `training_b1_shared_wsl.yaml`: spoločný adaptér `b1_shared_v2`.

Všetky používajú `configs/shared/models/qwen25_coder_7b_hf_wsl.yaml` a zapisujú
výstupy mimo repozitára. Postup: `docs/finetuning/v2_runbook.md`.
