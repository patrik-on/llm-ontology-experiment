# data/processed/refactoring

Finálny B2-R refactoring dataset vytvorený spojením ML4Refactoring a MaRV.

- `train.jsonl`: 4478 príkladov,
- `val.jsonl`: 600 príkladov,
- `test.jsonl`: 608 príkladov.

Používa sa pri refactoring fine-tuningu a evaluácii. Jednotný RAG index smie
čítať iba train split a musí zachovať pole `source`, aby bolo možné auditovať
pomer ML4Refactoring/MaRV vo výslednom kontexte.
