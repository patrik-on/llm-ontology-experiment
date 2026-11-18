# configs/shared/models

- `qwen25_coder_7b_ollama.yaml`: Ollama `qwen2.5-coder:7b`, runtime všetkých ramien okrem FT.
- `qwen25_coder_7b_hf_wsl.yaml`: lokálny Hugging Face model pre LoRA tréning a FT
  inferenciu (`${LLM_ONTOLOGY_MODELS_ROOT}/huggingface/Qwen2.5-Coder-7B-Instruct`).

Modelové váhy sú mimo repozitára a nesmú sa commitovať.
