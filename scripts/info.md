# scripts

Tenké CLI vstupy projektu. Nastavia import path, spracujú argumenty a zavolajú
implementáciu zo `src/llm_ontology/`.

| Priečinok | Účel |
|---|---|
| `datasets/` | inspect a prepare dataset pipeline |
| `finetuning/` | WSL/CUDA kontroly a QLoRA tréning |
| `inference/` | Ollama baseline a model setup |
| `evaluation/` | HF inference, metriky, reporty a analýzy |
| `retrieval/` | produkčný index builder, environment check a UI smoke |
| `experiments/` | benchmark orchestration a model × approach × task experimenty |

Benchmark smoke run:

```bash
python scripts/experiments/benchmarks/inspect_benchmarks.py
python scripts/experiments/benchmarks/run_benchmark.py \
  --benchmark testbench --limit 5 --backend prompt-only \
  --output artifacts/evaluation/runs/testbench_direct/predictions/testing/testbench_direct.jsonl
```

Produkčný retrieval index vytvorí `scripts/retrieval/build_production_indexes.py`.
Direct, RAG a
MultiRAG používa zdieľaný runner zo `src/`; samostatný duplicitný retrieval
runner sa v `scripts/` neudržiava.
