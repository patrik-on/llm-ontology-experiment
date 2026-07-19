# src/llm_ontology/retrieval

Spoločná provider-neutral retrieval infraštruktúra pre RAG a multi-RAG.

Plánované zodpovednosti:

- train-only corpus builder a document schema,
- code-aware chunking a fingerprinty,
- dense embeddings a persistent vector store,
- lexical/sparse retrieval,
- deduplikácia kandidátov,
- fusion a voliteľný reranker,
- retrieval trace a latency meranie.

Fáza 1 implementuje ChromaDB adaptér, deterministické dokumenty, deduplikáciu,
single-collection vector search, metadata filtre, train-only ochranu, context
budget a retrieval trace. Multi-collection fusion, routing, ontológia a
reranking zostávajú explicitne neimplementované. Retrieval nesmie importovať
model generation ani task metriky. RAG prompt composition patrí do
`llm_ontology.approaches`.
