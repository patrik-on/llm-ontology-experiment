# src/llm_ontology/data

Datasetové pipeline moduly.

- `methods2test.py`: spracovanie Methods2Test dát,
- `marv.py`: spracovanie MaRV refactoring dát,
- `ml4refactoring.py`: spracovanie ML4Refactoring ZIP projektov,
- `format.py`, `split.py`, `clean.py`: pomocné funkcie pre formátovanie, splitovanie a čistenie.

Výsledkom sú JSONL datasety v `data/processed/`.
