# configs/evaluation

Konfigurácie existujúcej baseline/LoRA evaluation pipeline.

- `eval_models.yaml`: baseline, v1 a v2 LoRA modely, generation a 4-bit runtime,
- `eval_models_v2_only.yaml`: baseline a finálne v2 adaptéry,
- `eval_testing.yaml`: testing dataset a výstupné priečinky,
- `eval_refactoring.yaml`: refactoring dataset a výstupné priečinky,
- `eval_full.yaml`: spoločný evaluation setup.

Inference pre každý model beží v samostatnom procese, aby sa uvoľnila VRAM.
Tieto configy zatiaľ reprezentujú existujúci direct inference tok. Budúci RAG
runner bude navyše zapisovať approach a retrieval trace; nemá sa pridávať ako
neprehľadný `if` blok do modelového zoznamu.
