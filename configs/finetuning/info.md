# configs/finetuning

LoRA/QLoRA tréningové konfigurácie.

- `lora_config.yaml`: LoRA, NF4 kvantizácia a training defaults,
- `training_b2_testing*.yaml`: testing-only model,
- `training_b2_refactoring*.yaml`: refactoring-only model,
- `training_b1_shared*.yaml`: shared testing + refactoring model.

Súbory s `_wsl` používajú lokálny model z
`configs/models/qwen25_coder_7b_hf_wsl.yaml` a zapisujú veľké výstupy mimo
Windows/OneDrive filesystemu. Varianty bez `_wsl` zostávajú pre Windows
readiness kontroly a kompatibilitu.

Fine-tuning je modelová os experimentu a je možné ho neskôr kombinovať s RAG.
