# src/llm_ontology

Knižničný kód projektu.

- `core/`: spoločné utility pre konfigurácie, cesty a logging,
- `data/`: spracovanie Methods2Test, MaRV a ML4Refactoring datasetov,
- `finetuning/`: prompt formatter, dataset loader a model loader,
- `inference/`: Ollama client a inference helpery,
- `evaluation/`: textové, testing a refactoring metriky plus report writer,
- `training/`: staršia alebo všeobecná tréningová infraštruktúra,
- `retrieval/`: miesto pre budúce RAG rozšírenia.
