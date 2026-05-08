# configs/evaluation

Konfigurácie evaluation pipeline.

- `eval_models.yaml`: baseline a LoRA modely/adaptéry, generation parametre a 4-bit/offload nastavenia.
- `eval_testing.yaml`: testing dataset a task nastavenia.
- `eval_refactoring.yaml`: refactoring dataset a task nastavenia.
- `eval_full.yaml`: kombinovaný evaluation setup.

`eval_models.yaml` podporuje `baseline_qwen25_coder_7b`, `b2_testing`, `b2_refactoring` a `b1_shared`.
