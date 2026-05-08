# src/llm_ontology/evaluation

Implementácia evaluation metrík a reportovania.

- `text_metrics.py`: základné textové podobnosti a dĺžky,
- `code_metrics.py`: Java-like proxy metriky pre kód,
- `test_metrics.py`: proxy metriky pre JUnit test generation,
- `refactoring_metrics.py`: code health, cohesion a coupling proxy metriky,
- `prediction_io.py`: čítanie/zápis JSONL predikcií,
- `report_writer.py`: Markdown report a ukážky,
- `inference_eval.py`: inference pre baseline a LoRA adaptéry,
- `metrics_runner.py`: CLI logika výpočtu metrík,
- `full_evaluation.py`: orchestrace inferencie, metrík a reportu,
- `smoke.py`: malý dummy smoke test evaluation pipeline,
- `coverage_runner.py`: placeholder pre budúcu reálnu JaCoCo coverage evaluáciu.

Aktuálne metriky sú proxy metriky, nie plná kompilácia alebo spustenie Java testov.
