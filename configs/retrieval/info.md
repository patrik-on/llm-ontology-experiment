# configs/retrieval

`base.yaml` je spustiteľná konfigurácia prvej RAG fázy pre ChromaDB, logické
názvy kolekcií, ochranu pred data leakage a retrieval limity. Provider
`deterministic_mock` slúži iba na overenie pipeline; nie je to sémantický model
vhodný pre reportované experimenty.

Spoločné retrieval nastavenia:

- embedding model a batch size,
- vector store a umiestnenie indexu,
- lexical alebo sparse retrieval,
- candidate count a final `top_k`,
- fusion a reranking,
- maximálny context token budget.

RAG aj multi-RAG majú zdieľať nastavenia, ktoré nie sú predmetom ablácie.
Evaluation index smie obsahovať iba train split. Indexy budú veľké lokálne
artefakty pod ignorovaným `artifacts/` alebo v externom output roote.
