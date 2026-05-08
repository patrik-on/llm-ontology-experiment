# configs/finetuning

Konfigurácie pre LoRA/QLoRA fine-tuning.

Hlavné súbory:

- `lora_config.yaml`: LoRA parametre, 4-bit quantization a training defaults,
- `training_b2_testing_wsl.yaml`: B2-T testing-only beh vo WSL,
- `training_b2_refactoring_wsl.yaml`: B2-R refactoring-only beh vo WSL,
- `training_b1_shared_wsl.yaml`: B1 shared beh vo WSL,
- súbory bez `_wsl`: Windows/relatívne varianty ponechané pre kompatibilitu.

WSL configy ukladajú checkpointy, logy a výsledky do `/home/patrik/experiments/llm-ontology`, nie do OneDrive-backed repozitára.
