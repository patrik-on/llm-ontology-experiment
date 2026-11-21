# Download links

Tento dokument zhromazduje verejne zdroje a externe artefakty potrebne na reprodukciu projektu.

## Base model

| Artefakt | Link | Poznamka |
|---|---|---|
| Qwen2.5-Coder-7B-Instruct | <https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct> | Base model pouzity pre baseline aj LoRA adaptery. |

Priklad stiahnutia cez Hugging Face CLI:

```bash
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct \
  --local-dir /mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

V aktualnych WSL configoch sa ocakava cesta:

```text
/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

Ak je model ulozeny inde, uprav `model_path` v:

- `configs/evaluation/eval_models.yaml`,
- `configs/finetuning/training_b2_testing_wsl.yaml`,
- `configs/shared/models/qwen25_coder_7b_hf_wsl.yaml` (všetky `training_*_wsl.yaml` ho používajú).

## Public datasets

| Dataset | Link | Pouzitie v projekte |
|---|---|---|
| Methods2Test | <https://github.com/microsoft/methods2test> | Zdroj pre `data/processed/testing/`, teda generovanie JUnit testov. |
| ML4Refactoring | <https://zenodo.org/records/3547639> | Zdroj pre velky refactoring subset `data/processed/refactoring_ml4ref/`. |
| MaRV Scripts and Dataset | <https://zenodo.org/records/14450098> | Zdroj pre manualne validovane refactoring priklady `data/processed/refactoring_marv/`. |

Plne spracovane JSONL splity nie su commitovane do Gitu. Male ukazky formatu su v `data/samples/`.

## LoRA adaptéry v3

Adaptéry vznikli v projekte a nie sú verejne dostupné. Odovzdávajú sa samostatne (napr. ZIP
celého priečinka `final_adapter`). Očakávané cesty sú v `configs/evaluation/eval_models.yaml`:

| Adaptér | Cesta |
|---|---|
| `b2_testing_v3` | `~/experiments/llm-ontology-v3/b2_testing/checkpoints/final_adapter` |
| `b2_refactoring_v3` | `~/experiments/llm-ontology-v3/b2_refactoring/checkpoints/final_adapter` |
| `b2_testing_onto` | `~/experiments/llm-ontology-v3/b2_testing_onto/checkpoints/final_adapter` |
| `b2_refactoring_onto` | `~/experiments/llm-ontology-v3/b2_refactoring_onto/checkpoints/final_adapter` |

Každý obsahuje aspoň `adapter_config.json` a `adapter_model.safetensors`; freeze matice ich
hashuje (`hf_identity/<adaptér>.json`). Tréning: `docs/finetuning/v3_runbook.md`.

## Minimal run without external artifacts

Bez modelu, datasetov a adapterov je stale mozne overit kod:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/benchmarks/run_testing_matrix.py --run-id model-check --dry-run
```

Evaluation entry points are documented in [current evaluation](../evaluation/README.md). Training/retrieval utilities do not define additional evaluation protocols.
