# scripts/inference

Samostatné inference utility mimo hlavného Hugging Face evaluation runnera.

- `check_model_setup.py`: overí Windows HF config, modelové súbory a Ollama,
- `run_ollama_baseline.py`: limitovaný Ollama baseline nad nakonfigurovanými dátami.

Canonical Direct/RAG/MultiRAG experiment sa spúšťa cez
`python -m llm_ontology.experiments.smoke`. Samostatná HF/LoRA evaluation má
vlastné príkazy pod `scripts/evaluation/`.
