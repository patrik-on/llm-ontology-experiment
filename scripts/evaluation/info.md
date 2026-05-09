# scripts/evaluation

CLI skripty pre evaluation pipeline.

- `run_inference_eval.py`: inference pre baseline/LoRA model na jednom datasete,
- `compute_eval_metrics.py`: výpočet testing/refactoring metrík,
- `build_eval_report.py`: Markdown report,
- `run_full_evaluation.py`: orchestrace inferencie, metrík a reportu,
- `smoke_eval_metrics.py`: malý dummy smoke test,
- `evaluate.py`: legacy wrapper, ktorý iba presmeruje na aktuálnu evaluation pipeline.

Hlavná logika je v `src/llm_ontology/evaluation/`.
