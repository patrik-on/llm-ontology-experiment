# data/processed/refactoring_marv

MaRV refactoring dataset.

- `train.jsonl`: 478 príkladov,
- `val.jsonl`: 100 príkladov,
- `test.jsonl`: 108 príkladov.

Záznamy majú `domain=refactoring`, `source=marv`, typ refaktoringu, commit
metadata a dostupné evaluation votes. Split je stratifikovaný podľa typu
refaktoringu; pred RAG fázou treba skontrolovať commit-level leakage.
