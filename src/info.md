# src

Knižničný Python kód projektu je v `src/llm_ontology/`.

| Modul | Zodpovednosť |
|---|---|
| `core/` | konfigurácie, cesty a logging |
| `data/` | dataset loading, čistenie, splitovanie a export |
| `models/` | model, tokenizer, kvantizácia a LoRA loading |
| `training/` | QLoRA training engine a readiness kontroly |
| `inference/` | prompting, approach runner a Ollama utility |
| `approaches/` | direct, RAG a multi-RAG prompt composition |
| `retrieval/` | budúce indexovanie, search, fusion a reranking |
| `evaluation/` | inference, task metriky, agregácie a reporty |
| `finetuning/` | kompatibilné pôvodné importy a dataset loader |

Implementačná logika patrí sem; `scripts/` majú zostať tenké CLI wrappery.
Architektonické hranice sú popísané v `docs/architecture.md`.
