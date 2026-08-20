# configs/retrieval

`base.yaml` je spustiteľná konfigurácia prvej RAG fázy pre ChromaDB, logické
názvy kolekcií, ochranu pred data leakage a retrieval limity. Provider
`deterministic_mock` slúži iba na overenie pipeline; nie je to sémantický model
vhodný pre reportované experimenty.

`ollama_bge_m3.yaml` je aktuálny WSL-only baseline s Ollamou na pevnom
`http://localhost:11434`, `bge-m3` (1024 rozmerov) a
`qwen2.5-coder:7b`.
Príprava modelu, produkčný leakage-safe builder a smoke validácia sú popísané v
`docs/ollama_embeddings.md`. Pôvodná Jina konfigurácia zostáva zachovaná ako
`legacy_not_final` a nie je predvoleným finálnym baseline.

Spoločné retrieval nastavenia:

- embedding model a batch size,
- vector store a umiestnenie indexu,
- lexical alebo sparse retrieval,
- candidate count a final `top_k`,
- fusion a reranking,
- maximálny context token budget.

RAG aj multi-RAG majú zdieľať nastavenia, ktoré nie sú predmetom ablácie.
Evaluation index smie obsahovať iba train split. Produkčné Chroma indexy sú
veľké lokálne artefakty pod ignorovaným `data/chroma/`; malé auditné manifesty
a reporty môžu byť publikované samostatne podľa artifact policy.
