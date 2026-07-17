# configs/datasets

Dataset-specific vstupy a limity spracovania.

`ml4refactoring.yaml` dokumentuje:

- umiestnenie veľkého externého archívu a rozbaleného datasetu,
- výstupný priečinok `data/processed/refactoring_ml4ref/`,
- cieľové veľkosti train/val/test,
- limity dĺžky vstupného a výstupného kódu,
- reprodukovateľný seed.

Modelové, retrieval ani evaluation nastavenia sem nepatria. Pred RAG fázou
treba doplniť group-split a deduplication audit na úrovni projektu/commitu.
