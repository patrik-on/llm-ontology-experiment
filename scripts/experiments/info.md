# scripts/experiments

Aktívna orchestration oblasť pre porovnávacie experimenty nad osami:

```text
model × generation approach × task
```

Podpriečinok `benchmarks/` obsahuje existujúce benchmark CLI a validáciu smoke
datasetu. Porovnania `direct`, `rag` a `multi_rag` musia používať rovnaký base
model a testovaciu množinu. RAG vetvy sa nesmú aktivovať bez train-only indexu
a retrieval trace.

Canonical resumable smoke CLI je modul
`python -m llm_ontology.experiments.smoke`; tento priečinok zostáva domovom
samostatných benchmark skriptov.

Tento priečinok obsahuje iba CLI orchestration. Model loading patrí do
`llm_ontology.models`, prompt composition do `llm_ontology.approaches`,
retrieval do `llm_ontology.retrieval` a metriky do `llm_ontology.evaluation`.
