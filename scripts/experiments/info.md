# scripts/experiments

Miesto pre porovnávací runner nad osami:

```text
model × generation approach × task
```

Prvá plánovaná CLI implementácia spustí `direct`, `rag` a `multi_rag` nad
rovnakým base modelom a testovacou množinou. RAG vetvy sa nesmú aktivovať bez
train-only indexu a retrieval trace.

Tento priečinok má obsahovať iba CLI orchestration. Model loading patrí do
`llm_ontology.models`, prompt composition do `llm_ontology.approaches`,
retrieval do `llm_ontology.retrieval` a metriky do `llm_ontology.evaluation`.
