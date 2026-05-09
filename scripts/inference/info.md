# scripts/inference

CLI skripty pre inferenciu mimo evaluation pipeline.

- `run_ollama_baseline.py`: C0 baseline cez Ollama,
- `check_model_setup.py`: kontrola lokálneho HF modelu a Ollama dostupnosti,
- `generate.py`: legacy wrapper, ktorý iba presmeruje na aktuálny `scripts/evaluation/run_inference_eval.py`.

Hlavná modelová inference pre baseline/LoRA porovnania je v `src/llm_ontology/evaluation/inference_eval.py`.
