# scripts/inference

Samostatné inference utility mimo hlavného Hugging Face evaluation runnera.

- `check_model_setup.py`: overí Windows HF config, modelové súbory a Ollama,
- `run_ollama_baseline.py`: limitovaný Ollama baseline nad nakonfigurovanými dátami,
- `generate.py`: legacy wrapper s navigáciou na aktuálnu evaluation pipeline.

Na hlavné baseline/LoRA porovnanie používaj `scripts/evaluation/`. Na budúce
direct/RAG/multi-RAG porovnanie bude slúžiť `scripts/experiments/`.
