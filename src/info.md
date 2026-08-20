# src

Knižničný Python kód projektu je v `src/llm_ontology/`.

| Modul | Zodpovednosť |
|---|---|
| `core/` | konfigurácie, cesty a logging |
| `datasets/` | dataset loading, čistenie, splitovanie a export |
| `benchmarks/` | read-only adaptéry TestBench a SWE-Refactor |
| `models/` | model, tokenizer, kvantizácia a LoRA loading |
| `finetuning/` | dataset formatter, QLoRA engine a readiness kontroly |
| `inference/` | prompting, approach runner a Ollama utility |
| `approaches/` | direct, RAG a multi-RAG prompt composition |
| `ingestion/` | retrieval corpus, manifesty, leakage a chunking |
| `vectorstore/` | Chroma persistence a collection lifecycle |
| `retrieval/` | search, RRF fusion, token budget a trace |
| `evaluation/` | inference evaluation, task metriky, agregácie a reporty |
| `ui/` | Gradio prezentácia a environment status |

Implementačná logika patrí sem; `scripts/` zostávajú tenké CLI wrappery.
Architektonické hranice sú v `docs/architecture/system_architecture.md`.
