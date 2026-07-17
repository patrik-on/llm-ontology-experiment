# src/llm_ontology/inference

Spoločná inferenčná vrstva nezávislá od konkrétneho experimentu.

- `prompting/`: jednotný instruction prompt pre training a inference,
- `approach_runner.py`: výber direct/RAG/multi-RAG prompt composition,
- `prompts.py`: kompatibilné high-level prompt helpery,
- `ollama_client.py`: HTTP klient pre Ollama,
- `ollama_baseline.py`: limitovaný Ollama runner,
- `model_setup_check.py`: kontrola modelových configov a lokálneho runtime,
- `generate.py`: legacy navigácia.

Hugging Face/LoRA model execution je zatiaľ v evaluation runneri. Pri ďalšom
refaktore sa backend oddelí tak, aby direct, RAG a multi-RAG používali rovnaké
generovanie a líšili sa iba pripraveným kontextom.
