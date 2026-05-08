# scripts/inference

CLI skripty pre inferenciu mimo evaluation pipeline.

- `run_ollama_baseline.py`: C0 baseline cez Ollama,
- `check_model_setup.py`: kontrola lokálneho HF modelu a Ollama dostupnosti,
- `generate.py`: starší generický generate entrypoint.

Hlavná logika je v `src/llm_ontology/inference/`.
