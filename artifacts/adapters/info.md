# artifacts/adapters

Dokumentácia a malé handoff metadata pre finálne v2 LoRA adaptéry:

- `b2_testing_v2`,
- `b2_refactoring_v2`,
- `b1_shared_v2`.

Commitovateľné sú `v2_adapter_zip_manifest.json` a `.sha256` checksumy. Samotné
ZIP balíky a `adapter_model.safetensors` zostávajú mimo Gitu.

Vytvorenie balíkov:

```bash
python scripts/package_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --output-dir artifacts/adapters
```

Kontrola rozbalených adapterov:

```bash
python scripts/check_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml
```

Každý adapter potrebuje minimálne `adapter_config.json`,
`adapter_model.safetensors` a `tokenizer_config.json`.
