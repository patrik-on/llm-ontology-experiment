# data/processed

Finálne spracované datasety vo formáte JSONL.

- `testing/`: Methods2Test subset pre JUnit test generation, 4000/500/500.
- `refactoring_ml4ref/`: ML4Refactoring subset, 4000/500/500.
- `refactoring_marv/`: MaRV refactoring dataset, 478/100/108.
- `refactoring/`: finálny B2-R dataset, ML4Refactoring + MaRV, 4478/600/608.
- `combined/`: finálny B1 shared dataset, Methods2Test + ML4Refactoring, 8000/1000/1000.

Tieto súbory nemení tréning ani evaluation pipeline.

Malé ukážky formátu sú v `data/samples/`, aby boli viditeľné aj na GitHube bez commitovania plných datasetov.
