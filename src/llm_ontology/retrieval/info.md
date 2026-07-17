# src/llm_ontology/retrieval

Budúca spoločná retrieval infraštruktúra pre RAG a multi-RAG.

Plánované zodpovednosti:

- train-only corpus builder a document schema,
- code-aware chunking a fingerprinty,
- dense embeddings a persistent vector store,
- lexical/sparse retrieval,
- deduplikácia kandidátov,
- fusion a voliteľný reranker,
- retrieval trace a latency meranie.

Aktuálne sú implementované iba approach kontrakty; indexovanie a search backend
ešte nie sú hotové. Retrieval nesmie importovať model generation ani task
metriky. RAG prompt composition patrí do `llm_ontology.approaches`.
