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
- `configs/evaluation/eval_models_v2_only.yaml`,
- `configs/finetuning/training_b2_testing_wsl.yaml`,
- `configs/finetuning/training_b2_refactoring_wsl.yaml`,
- `configs/finetuning/training_b1_shared_wsl.yaml`.

## Public datasets

| Dataset | Link | Pouzitie v projekte |
|---|---|---|
| Methods2Test | <https://github.com/microsoft/methods2test> | Zdroj pre `data/processed/testing/`, teda generovanie JUnit testov. |
| ML4Refactoring | <https://zenodo.org/records/3547639> | Zdroj pre velky refactoring subset `data/processed/refactoring_ml4ref/`. |
| MaRV Scripts and Dataset | <https://zenodo.org/records/14450098> | Zdroj pre manualne validovane refactoring priklady `data/processed/refactoring_marv/`. |

Plne spracovane JSONL splity nie su commitovane do Gitu. Male ukazky formatu su v `data/samples/`.

## V2 LoRA adapters

Tieto adaptery vznikli v projekte a nie su verejne dostupne cez upstream dataset/model stranky. Treba ich odovzdat separatne, napriklad ako GitHub Release asset, Google Drive/OneDrive ZIP alebo skolsky upload.

| Adapter | Ocakavana cesta v aktualnom configu | Odporucany nazov ZIP suboru |
|---|---|---|
| `b2_testing_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter` | `b2_testing_v2_final_adapter.zip` |
| `b2_refactoring_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter` | `b2_refactoring_v2_final_adapter.zip` |
| `b1_shared_v2` | `/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter` | `b1_shared_v2_final_adapter.zip` |

Po rozbaleni musi kazdy adapter obsahovat:

```text
adapter_config.json
adapter_model.safetensors
tokenizer_config.json
```

Kontrola:

```bash
python scripts/check_v2_adapters.py --models-config configs/evaluation/eval_models_v2_only.yaml
```

Ak budu adaptery ulozene na inych cestach, uprav `adapter_path` v `configs/evaluation/eval_models_v2_only.yaml`.

ZIP subory sa daju vytvorit z lokalnych adapterov prikazom:

```bash
python scripts/package_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --output-dir artifacts/adapters
```

Skript vytvori:

- `artifacts/adapters/b2_testing_v2_final_adapter.zip`,
- `artifacts/adapters/b2_refactoring_v2_final_adapter.zip`,
- `artifacts/adapters/b1_shared_v2_final_adapter.zip`,
- `.sha256` checksum subory,
- `artifacts/adapters/v2_adapter_zip_manifest.json`.

ZIP subory zostavaju mimo Gitu, ale `.sha256` a manifest su male textove subory vhodne na commit.

## Minimal run without external artifacts

Bez modelu, datasetov a adapterov je stale mozne overit kod:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/evaluation/smoke_eval_metrics.py
```

## Model evaluation after downloads

Po stiahnuti base modelu, priprave test datasetov a rozbaleni adapterov:

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --limit 5 \
  --output-root evaluation_v2_smoke \
  --overwrite
```

Finalny limit 50/100 spustaj az po tom, co prejde smoke beh.
