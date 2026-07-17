# data/processed/refactoring_ml4ref

ML4Refactoring subset s before/after Java pármi.

- `train.jsonl`: 4000 príkladov,
- `val.jsonl`: 500 príkladov,
- `test.jsonl`: 500 príkladov.

Záznamy majú `domain=refactoring`, `source=ml4refactoring` a metadata projektu,
commitu, súboru a typu refaktoringu. Aktuálny split vznikol náhodným delením
záznamov; pred RAG evaluáciou treba auditovať rovnaké projekty/commity a code
fingerprinty naprieč splitmi.
