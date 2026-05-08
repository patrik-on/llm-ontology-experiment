# src/llm_ontology/inference

Inferenčný pomocný kód.

- `ollama_client.py`: HTTP klient pre Ollama `/api/generate`,
- `ollama_baseline.py`: runner pre C0 Ollama baseline predikcie,
- `model_setup_check.py`: kontrola lokálneho HF modelu a Ollama dostupnosti,
- `prompts.py`: prompt helpery,
- `generate.py`: všeobecné generovanie.

Fine-tuned Hugging Face evaluation inferenciu riadi hlavne `scripts/evaluation/run_inference_eval.py`.

