# configs

Tento priečinok obsahuje YAML konfigurácie projektu. Sú rozdelené podľa účelu:

- `models/`: lokálne Hugging Face a Ollama modely,
- `finetuning/`: LoRA/QLoRA a tréningové konfigurácie,
- `inference/`: baseline inference cez Ollama,
- `evaluation/`: modely, datasety a parametre evaluation pipeline,
- `datasets/`: datasetové konfigurácie,
- `experiments/`: staršie alebo pomocné experiment configy,
- `templates/`: šablóny pre budúce rozšírenia, napríklad RAG.

Pre reálny WSL fine-tuning používaj primárne `configs/finetuning/*_wsl.yaml`.
