# scripts

Spustiteľné CLI skripty projektu.

Najdôležitejšie skupiny:

- príprava dát: `prepare_*.py`, `inspect_*.py`,
- fine-tuning: `train_finetuning.py`, `check_finetuning_ready.py`, `check_transformers_compat.py`,
- baseline inference: `run_ollama_baseline.py`,
- evaluation: `run_inference_eval.py`, `compute_eval_metrics.py`, `build_eval_report.py`, `run_full_evaluation.py`, `smoke_eval_metrics.py`.

`run_full_evaluation.py` spúšťa každý model v samostatnom procese, aby sa uvoľnila GPU pamäť medzi modelmi.
