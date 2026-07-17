# src/llm_ontology/evaluation

Inference, metriky, agregácie a reportovanie.

- `inference_eval.py`: Hugging Face baseline a LoRA generovanie,
- `prediction_io.py`: normalizovaná JSONL/JSON/CSV schéma,
- `test_metrics.py`: JUnit štrukturálne proxy metriky,
- `refactoring_metrics.py`: refactoring quality proxy,
- `text_metrics.py` a `code_metrics.py`: spoločné text/code signály,
- `metrics_runner.py`: per-example a aggregate výpočty,
- `report_writer.py`: report a kvalitatívne ukážky,
- `full_evaluation.py`: subprocess orchestration,
- `smoke.py`: model-free end-to-end kontrola,
- `coverage_runner.py`: placeholder pre executable JaCoCo subset.

Staršie `metrics.py`, `testing.py`, `refactoring.py` a `report.py` zostávajú pre
kompatibilitu. Nové RAG vyhodnotenie doplní retrieval trace, Recall/MRR tam,
kde existuje relevance, a efficiency metriky. Proxy skóre nie sú náhradou
kompilácie alebo behavior preservation.
