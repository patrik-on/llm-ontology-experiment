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

## Source layout

```text
src/llm_ontology/
├── core/          spoločná konfigurácia, cesty a logging
├── data/          príprava a validácia datasetov
├── models/        model, tokenizer, kvantizácia a LoRA loading
├── training/      fine-tuning workflow
├── inference/     modelové backendy a spoločné promptovanie
├── approaches/    direct, RAG a multi-RAG zostavenie kontextu
├── retrieval/     indexovanie a vyhľadávanie; implementuje sa v ďalšej fáze
└── evaluation/    task metriky, agregácie a reporty
```

Fine-tuning nie je generation approach. Mení váhy modelu, preto zostáva v
`training/` a `models/`. RAG mení kontext pred generovaním, preto patrí do
`approaches/` a `retrieval/`.

## Compatibility

Existujúce CLI príkazy a importy zostávajú funkčné. Staré moduly pod
`finetuning/` môžu dočasne re-exportovať implementáciu z nových spoločných
modulov. Odstránia sa až po migrácii všetkých interných importov a runbookov.

## Experimental safety

- Retrieval index pre evaluáciu smie obsahovať iba train split.
- Val split slúži na ladenie top-k, fusion a rerankingu.
- Test split sa použije až po zmrazení konfigurácie.
- Každá predikcia bude v retrieval fáze obsahovať ID, zdroj, rank a score
  použitých kontextov.
