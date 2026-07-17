# configs/inference

Konfigurácie samostatnej lokálnej inferencie mimo hlavného Hugging Face
evaluation toku.

`ollama_qwen25_coder_baseline.yaml` používa modelový config
`configs/models/qwen25_coder_7b_ollama.yaml`, limitované testovacie datasety a
zapisuje JSONL predikcie.

Ollama slúži na rýchly baseline a prompt testing. Fine-tuning používa Hugging
Face/PEFT a hlavné porovnanie modelov používa `scripts/evaluation/`.
