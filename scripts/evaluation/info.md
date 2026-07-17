# scripts/evaluation

CLI vrstva aktuálnej baseline/LoRA evaluation pipeline.

- `run_inference_eval.py`: Hugging Face baseline alebo PEFT LoRA predikcie,
- `compute_eval_metrics.py`: per-example a aggregate metriky,
- `build_eval_report.py`: Markdown report a kvalitatívne ukážky,
- `run_full_evaluation.py`: inference → metrics → report,
- `smoke_eval_metrics.py`: model-free end-to-end smoke test,
- `check_v2_adapters.py`: kontrola súborov adapterov,
- `analyze_interference.py`: cross-task/interference analýza,
- `analyze_lora_adapters.py`: normy a podobnosť LoRA váh,
- `evaluate.py`: legacy navigácia; nepoužívať na nové behy.

Proxy metriky nenahrádzajú Java kompiláciu, test execution, JaCoCo ani
behavior preservation. Budúci RAG report navyše potrebuje retrieval trace,
latency, token counts a retrieval metriky.

```bash
python scripts/evaluation/smoke_eval_metrics.py
```
