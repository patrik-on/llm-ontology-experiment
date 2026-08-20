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
| `retrieval/` | produkčný index builder, environment check a UI smoke |
| `experiments/` | poznámky k model × approach × task experimentom |

Benchmark smoke run:

```bash
python scripts/benchmarks/inspect_benchmarks.py
python scripts/benchmarks/run_benchmark.py \
  --benchmark testbench --limit 5 --backend prompt-only \
  --output evaluation/predictions/testbench_direct.jsonl
```

Produkčný retrieval index vytvorí `build_production_indexes.py`. Direct, RAG a
MultiRAG používa zdieľaný runner zo `src/`; samostatný duplicitný retrieval
runner sa v `scripts/` neudržiava.
