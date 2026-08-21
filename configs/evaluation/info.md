# configs/evaluation

Konfigurácie existujúcej baseline/LoRA evaluation pipeline.

- `eval_models.yaml`: baseline, v1 a v2 LoRA modely, generation a 4-bit runtime,
- `eval_models_v2_only.yaml`: baseline a finálne v2 adaptéry,
- `eval_testing.yaml`: testing dataset a výstupné priečinky,
- `eval_refactoring.yaml`: refactoring dataset a výstupné priečinky,
- `eval_full.yaml`: spoločný evaluation setup.

Canonical výstup je `artifacts/evaluation/runs/<run_id>/`. `run_id` je
validovaný názov experimentu; konfigurácie ani príkazy už neurčujú ľubovoľný
top-level `output_root`.

Inference pre každý model beží v samostatnom procese, aby sa uvoľnila VRAM.
Tieto Hugging Face/LoRA configy sú `legacy_not_final` a reprezentujú historický
direct inference tok. Aktuálny WSL/Ollama Direct/RAG/MultiRAG baseline používa
configy v `configs/experiments/rag_v2/` a spoločný experiment runner.
