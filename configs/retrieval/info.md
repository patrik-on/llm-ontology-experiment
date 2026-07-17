# configs/retrieval

Miesto pre spoločné retrieval nastavenia:

- embedding model a batch size,
- vector store a umiestnenie indexu,
- lexical alebo sparse retrieval,
- candidate count a final `top_k`,
- fusion a reranking,
- maximálny context token budget.

RAG aj multi-RAG majú zdieľať tie nastavenia, ktoré nie sú predmetom ablácie.
Evaluation index smie obsahovať iba train split. Indexy sú veľké lokálne
artefakty a patria pod ignorovaný artifact/index alebo externý output root.
