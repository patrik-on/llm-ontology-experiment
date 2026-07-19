# scripts

Tenké CLI vstupy projektu. Nastavia import path, spracujú argumenty a zavolajú
implementáciu zo `src/llm_ontology/`.

| Priečinok | Účel |
|---|---|
| `data/` | inspect a prepare dataset pipeline |
| `training/` | WSL/CUDA kontroly a QLoRA tréning |
| `inference/` | Ollama baseline a model setup |
| `benchmarks/` | inventár a direct benchmark runner |
| `evaluation/` | HF inference, metriky, reporty a analýzy |
| `experiments/` | budúce model × approach × task experimenty |

Benchmark smoke run:

```bash
python scripts/benchmarks/inspect_benchmarks.py
python scripts/benchmarks/run_benchmark.py \
  --benchmark testbench --limit 5 --backend prompt-only \
  --output evaluation/predictions/testbench_direct.jsonl
```

Retrieval indexing a porovnávací RAG runner sa pridajú v samostatnej fáze.
