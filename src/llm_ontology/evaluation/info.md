# src/llm_ontology/evaluation

Implementácia evaluation metrík a reportovania.

- `text_metrics.py`: základné textové podobnosti a dĺžky,
- `code_metrics.py`: Java-like proxy metriky pre kód,
- `test_metrics.py`: proxy metriky pre JUnit test generation,
- `refactoring_metrics.py`: code health, cohesion a coupling proxy metriky,
- `prediction_io.py`: čítanie/zápis JSONL predikcií,
- `report_writer.py`: Markdown report a ukážky,
- `coverage_runner.py`: placeholder pre budúcu reálnu JaCoCo coverage evaluáciu.

Aktuálne metriky sú proxy metriky, nie plná kompilácia alebo spustenie Java testov.
