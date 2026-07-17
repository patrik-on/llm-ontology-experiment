# data/raw

Pôvodné Methods2Test, MaRV a ML4Refactoring dáta a archívy. Obsah môže byť
veľký a zostáva mimo Gitu.

Raw dáta sa neupravujú ručne. Na kontrolu a spracovanie používaj skripty v
`scripts/data/`. Reprodukovateľný výstup patrí do `data/processed/`.

Retrieval index sa nesmie stavať priamo z nekontrolovaných raw dát; corpus
builder má používať validované train splity a zachovať provenance metadata.
