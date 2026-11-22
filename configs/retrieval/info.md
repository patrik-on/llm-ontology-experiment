# configs/retrieval

- `ollama_bge_m3_v3.yaml` je **jediná aktuálna** RAG konfigurácia (WSL Ollama,
  `bge-m3`, `qwen2.5-coder:7b`, index `data/chroma/ollama_bge_m3_v3`). Používajú ju
  obe matice, `python -m llm_ontology.env check` aj
  `scripts/retrieval/build_production_indexes.py`. Postup: `docs/retrieval/rag_v3.md`.
- `base.yaml` je testovacia konfigurácia s `deterministic_mock` providerom pre
  unit testy pipeline; nie je to sémantický model pre experimenty.

Staršie V1/V2 a Jina konfigurácie boli odstránené (sú v Git histórii, opis v
`docs/archive/retrieval/`). Evaluation index smie obsahovať iba train split;
Chroma indexy sú lokálne pod ignorovaným `data/chroma/`.
