# Project architecture

Projekt oddeľuje tri nezávislé osi experimentu:

1. **Model**: base Qwen alebo Qwen s LoRA adaptérom.
2. **Generation approach**: direct, RAG alebo multi-RAG.
3. **Task**: generovanie JUnit testov alebo refaktoring.

Experiment je ich kompozícia, napríklad:

```text
baseline_qwen25_coder_7b × direct × testing
baseline_qwen25_coder_7b × rag × testing
b2_testing_v2 × rag × testing
```

Fine-tuning mení váhy modelu. RAG mení vstupný kontext. Preto sú to dve
nezávislé osi a možno ich kombinovať bez duplikovania pipeline.

## Source layout

```text
src/llm_ontology/
├── core/          spoločná konfigurácia, cesty (${LLM_ONTOLOGY_*} premenné), logging
├── datasets/      príprava a validácia Methods2Test, MaRV a ML4Refactoring, splity
├── benchmarks/    dve evaluačné matice (testing, refactoring) a ich interné helpery
├── evaluation/    HF inference, JaCoCo coverage runner, experiment log, run layout
├── models/        model, tokenizer, kvantizácia a LoRA loading
├── finetuning/    prompt formatter, dataset loader a QLoRA tréning (training/)
├── inference/     Ollama klient, spoločné promptovanie, structured output
├── approaches/    direct, RAG a multi-RAG zostavenie kontextu
├── ingestion/     manifesty, leakage audit, Java parsing a pair-aware corpus
├── providers/     Ollama, mock a Sentence Transformers embeddings
├── retrieval/     single/multi-collection retrieval, RRF, reranking a token budget
├── vectorstore/   Chroma adaptér, lifecycle a sidecar manifesty
├── env/           kontrola runtime prostredia (`python -m llm_ontology.env check`)
└── cli/           RAG CLI
```

Lokálne benchmarkové checkouty (`benchmarks/swe-refactor/`) a veľké dáta sú
mimo Gitu. Kód v `src/llm_ontology/benchmarks/` ich iba číta; pôvodné projekty
neupravuje. Mapa zodpovedností je v [project_map.md](project_map.md).

## Benchmark flow

```text
dataset → deterministický výber + QA hodnotiteľa → zmrazený prompt pre každé rameno
        → jedna generácia (Ollama alebo HF/PEFT) → kompilácia / vykonanie / detekcia
        → artifacts/evaluation/runs/<run-id>/reports/
```

Ramená: `qwen_base`, `onto_project`, `skills`, `skills_onto`, `rag_single`, `ft_*`,
`ft_v3_onto`, `ft_onto`. Detaily sú v
[eval dokumentácii](../evaluation/README.md).

## Retrieval safety

- Retrieval index pre evaluáciu smie obsahovať iba train split.
- Val split slúži na ladenie top-k a fusion pred baseline freeze.
- Test split a benchmarkové prípady sa nesmú indexovať.
- Každá RAG/MultiRAG predikcia obsahuje retrieval trace.

## Implemented RAG/MultiRAG flow

RAG je zakomponovaný do pôvodných architektonických hraníc, nie ako druhá
inference pipeline:

```text
data -> ingestion -> vectorstore -> retrieval -> approaches -> inference
                                          |
                                          +-> evaluation experiment record
```

- `datasets/` naďalej vlastní datasety a ich splity,
- `ingestion/` pridáva loader/chunker rozhrania a train-only guard,
- `vectorstore/` izoluje ChromaDB API,
- `retrieval/` vlastní request, filtre, token budget a trace,
- `approaches/` naďalej vlastní direct/RAG/multi-RAG prompt kompozíciu,
- `inference/` kombinuje retrieval výsledok s LLM providerom,
- `evaluation/` ukladá reprodukovateľné experimentálne záznamy.

Aktuálny retrieval (task-aware query, reranking, index) je v
[RAG v3](../retrieval/rag_v3.md). Staršie fázy sú v `docs/retrieval/archive/`.

## Compatibility

Existujúce CLI príkazy a importy zostávajú funkčné. Moduly pod `finetuning/`
dočasne re-exportujú spoločnú modelovú a promptovaciu implementáciu.
