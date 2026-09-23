# Retrieval V3

V3 opravuje tri konkrétne nedostatky zistené pri analýze `baseline_v2` bez
prepísania jeho zmrazených artefaktov.

## Čo sa zmenilo

1. Query už nie je iba surový Java kód. `task_aware_v1` pridá typ úlohy,
   názov triedy, focal method, požiadavky a až potom vstupný kód. Používa iba
   informácie, ktoré sú už viditeľné v benchmarkovom prompte.
2. Párové záznamy sa už neembedujú ako spoločný vstup a referenčný výstup.
   Embedding template `2` indexuje iba pôvodný/produkčný kód a typ úlohy.
   Kompletný pár zostáva v `content`, takže po nájdení správneho príkladu dostane
   model vstup aj jeho test alebo refaktorovaný výsledok.
3. Chroma načíta 12 dense kandidátov a doplní kandidátov s presným názvom focal
   method. Kandidáti sa deduplikujú podľa produkčnej/pôvodnej metódy a
   `code_aware_v1` ich deterministicky preradí podľa dense skóre, lexikálnej
   podobnosti a základného tvaru Java metódy. Do promptu idú až finálne tri
   príklady. Reranker zámerne porovnáva iba vstupnú stranu evidencie, aby
   referenčný výstup nemohol umelo zvýšiť skóre.

## Izolácia od V2

- konfigurácia: `configs/retrieval/ollama_bge_m3_v3.yaml`,
- pipeline verzia: `rag-v3`,
- embedding template verzia: `2`,
- nový index: `data/chroma/ollama_bge_m3_v3`.

Existujúci `baseline_v2`, jeho fingerprint a index
`data/chroma/ollama_bge_m3_v2` zostávajú nezmenené.

## Vytvorenie nového indexu

Vo WSL, s aktívnym `.venv_wsl` a spustenou Ollamou:

```bash
python scripts/retrieval/build_production_indexes.py \
  --config configs/retrieval/ollama_bge_m3_v3.yaml \
  --report artifacts/retrieval/indexes/ollama_bge_m3_v3_production_report.json
```

Tento krok volá iba embedding model `bge-m3`; negeneruje odpovede cez
`qwen2.5-coder:7b`. Až po úspešnom rebuilde a kontrole manifestov sa má vytvoriť
a zmraziť samostatný `baseline_v3.yaml`. V2 konfigurácia sa na V3 nesmie
prepisovať.
