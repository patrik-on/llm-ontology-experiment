# src/llm_ontology/data

Reprodukovateľná dataset pipeline.

- `methods2test.py`: oficiálne Methods2Test splity a filtering,
- `marv.py`: MaRV validácia a stratifikovaný split,
- `ml4refactoring.py`: bezpečné ZIP rozbalenie a before/after páry,
- `final_datasets.py`: finálny B2-R a B1 mix,
- `format.py`, `split.py`, `clean.py`, `download.py`: spoločné utility.

Výstupom sú JSONL súbory v `data/processed/`. Táto vrstva nepripravuje RAG
indexy. Budúci corpus builder bude čítať validované train splity a pridá
fingerprinty, provenance a leakage kontroly.
