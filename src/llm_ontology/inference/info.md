# src/llm_ontology/inference

Spoločná inferenčná vrstva nezávislá od konkrétneho experimentu.

- `prompting/`: jednotný instruction prompt pre training a inference
  (aktívny testing profil `testing_bodies_one_shot_v2.py`),
- `ollama_client.py`: HTTP klient pre Ollama.

Generovanie vlastnia dve evaluačné matice (`scripts/benchmarks/`), nie samostatný
runner. Hugging Face/LoRA volania sú v `llm_ontology.evaluation.hf_inference`.
