# scripts

CLI vstupy projektu. Skripty majú byť tenké: nastavia import path, spracujú
argumenty a zavolajú implementáciu zo `src/llm_ontology/`.

| Priečinok | Účel |
|---|---|
| `data/` | inspect a prepare dataset pipeline |
| `training/` | WSL/CUDA kontroly a QLoRA tréning |
| `inference/` | Ollama baseline, model setup a legacy navigácia |
| `evaluation/` | HF inference, metriky, reporty a analýzy |
| `experiments/` | budúci model × approach × task runner |

Root wrappery ako `scripts/train_finetuning.py` a
`scripts/run_full_evaluation.py` ostávajú pre pohodlné a spätne kompatibilné
príkazy.

## Bežný tok

```bash
python scripts/data/prepare_methods2test.py
python scripts/data/prepare_ml4refactoring.py
python scripts/data/prepare_marv.py
python scripts/data/prepare_final_datasets.py

python scripts/training/check_transformers_compat.py
python scripts/training/debug_prompt_masking.py

python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --limit 50 \
  --output-root evaluation_v2_only \
  --overwrite
```

Retrieval indexing a porovnávací runner sa pridajú do samostatných CLI vrstiev;
nebudú kopírovať existujúcu inference alebo evaluation logiku.
