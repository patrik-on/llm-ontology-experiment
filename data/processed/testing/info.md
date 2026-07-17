# data/processed/testing

Finálny Methods2Test subset pre generovanie JUnit testov.

- `train.jsonl`: 4000 príkladov,
- `val.jsonl`: 500 príkladov,
- `test.jsonl`: 500 príkladov.

Záznamy majú `domain=testing`, `source=methods2test` a typicky
`context_level=src_fm`. Oficiálne Methods2Test splity sa zachovávajú.

Budúci testing retrieval corpus smie používať iba `train.jsonl`.
