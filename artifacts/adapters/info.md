# Adapter artifacts

Tento priecinok je urceny iba na dokumentaciu a male manifesty k adapterom. Samotne LoRA vahy sa do Gitu necommitujú, pretoze `adapter_model.safetensors` je binarny modelovy artefakt.

Verejne zdroje a odporucane download odkazy su zhrnute v `docs/download_links.md`.

## V2 adaptery

Finalne v2 adaptery boli vytvorene mimo repozitara:

| Model | Cesta |
|---|---|
| `b2_testing_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter` |
| `b2_refactoring_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter` |
| `b1_shared_v2` | `/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter` |

Kazdy adapter ma mat:

- `adapter_config.json`,
- `adapter_model.safetensors`,
- `tokenizer_config.json`.

Orientacna velkost kazdeho adapter directory je priblizne 50 MB.

Odporucane nazvy ZIP suborov pre odovzdanie:

- `b2_testing_v2_final_adapter.zip`,
- `b2_refactoring_v2_final_adapter.zip`,
- `b1_shared_v2_final_adapter.zip`.

Vytvorenie ZIPov:

```bash
python scripts/package_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --output-dir artifacts/adapters
```

Skript vytvori aj `.sha256` checksumy a `v2_adapter_zip_manifest.json`.

## Kontrola

Ak su adaptery dostupne na cestach z evaluation configu:

```bash
python scripts/check_v2_adapters.py --models-config configs/evaluation/eval_models_v2_only.yaml
```

Ak su skopirovane inde, uprav `adapter_path` v `configs/evaluation/eval_models_v2_only.yaml`.
