# src/llm_ontology/inference

Spoločná inferenčná vrstva nezávislá od konkrétneho experimentu.

- `prompting/`: jednotný instruction prompt pre training a inference,
- `approach_runner.py`: výber direct/RAG/multi-RAG prompt composition,
- `prompts.py`: kompatibilné high-level prompt helpery,
- `ollama_client.py`: HTTP klient pre Ollama,
- `ollama_baseline.py`: limitovaný Ollama runner,
- `model_setup_check.py`: kontrola modelových configov a lokálneho runtime.

Direct, RAG a MultiRAG používajú spoločný `RagExperimentRunner`, canonical
prompt builder a generation boundary; režimy sa líšia iba retrieval kontextom.
Hugging Face/LoRA model execution zostáva v samostatnom evaluation runneri.
