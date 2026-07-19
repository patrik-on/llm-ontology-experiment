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
├── core/          spoločná konfigurácia, cesty a logging
├── data/          príprava a validácia datasetov
├── benchmarks/    read-only adaptéry TestBench a SWE-Refactor
├── models/        model, tokenizer, kvantizácia a LoRA loading
├── training/      fine-tuning workflow
├── inference/     modelové backendy a spoločné promptovanie
├── approaches/    direct, RAG a multi-RAG zostavenie kontextu
├── retrieval/     budúce indexovanie a vyhľadávanie
└── evaluation/    task metriky, agregácie a reporty
```

`benchmarks/` v koreni je vendored evaluation obsah. Kód v
`src/llm_ontology/benchmarks/` ho iba číta a normalizuje; pôvodné skripty ani
projekty neupravuje.

## Benchmark flow

```text
vendored benchmark → read-only adapter → BenchmarkCase
                                         ↓
                                  direct prompt → model → prediction
```

TestBench `source/simple/full context` je kontrolovaná vlastnosť vstupu úlohy.
SWE-Refactor adaptér uchováva referenčný výstup a compile/project metadata.

## Future retrieval safety

- Retrieval index pre evaluáciu smie obsahovať iba train split.
- Val split bude slúžiť na ladenie top-k, fusion a rerankingu.
- Test split a benchmarkové prípady sa nesmú indexovať.
- Každá budúca RAG predikcia musí obsahovať retrieval trace.

## Implemented RAG phase-1 flow

RAG je zakomponovaný do pôvodných architektonických hraníc, nie ako druhá
inference pipeline:

```text
data -> ingestion -> vectorstore -> retrieval -> approaches -> inference
                                          |
                                          +-> evaluation experiment record
```

- `data/` naďalej vlastní datasety a ich splity,
- `ingestion/` pridáva loader/chunker rozhrania a train-only guard,
- `vectorstore/` izoluje ChromaDB API,
- `retrieval/` vlastní request, filtre, token budget a trace,
- `approaches/` naďalej vlastní direct/RAG/multi-RAG prompt kompozíciu,
- `inference/` kombinuje retrieval výsledok s LLM providerom,
- `evaluation/` ukladá reprodukovateľné experimentálne záznamy.

Podrobný stav, CLI a explicitné obmedzenia sú v [RAG phase 1](rag_phase1.md).

## Compatibility

Existujúce CLI príkazy a importy zostávajú funkčné. Moduly pod `finetuning/`
dočasne re-exportujú spoločnú modelovú a promptovaciu implementáciu.
