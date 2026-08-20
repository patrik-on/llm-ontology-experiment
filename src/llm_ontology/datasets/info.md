# src/llm_ontology/datasets

Reprodukovateľná dataset pipeline.

- `methods2test.py`: oficiálne Methods2Test splity a filtering,
- `marv.py`: MaRV validácia a stratifikovaný split,
- `ml4refactoring.py`: bezpečné ZIP rozbalenie a before/after páry,
- `final_datasets.py`: finálny B2-R a B1 mix,
- `format.py`, `split.py`, `clean.py`, `download.py`: spoločné utility.

Výstupom sú JSONL súbory v `data/processed/`. Táto vrstva nepripravuje RAG
indexy. Retrieval corpus builder číta validované train splity cez samostatnú
`ingestion/` hranicu a pridáva fingerprinty, provenance a leakage kontroly.
