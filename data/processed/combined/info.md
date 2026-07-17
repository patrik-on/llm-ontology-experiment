# data/processed/combined

Balanced B1 shared dataset:

- train: 4000 Methods2Test + 4000 ML4Refactoring,
- val: 500 Methods2Test + 500 ML4Refactoring,
- test: 500 Methods2Test + 500 ML4Refactoring.

Celkové počty sú 8000/1000/1000. MaRV nie je súčasťou combined datasetu.

Tento mix je určený pre shared fine-tuning. Pre kontrolované RAG porovnanie sa
majú budovať explicitné source kolekcie z pôvodných train datasetov, nie
automaticky indexovať combined val alebo test dáta.
