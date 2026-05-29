# Reproducible handoff

Tento dokument popisuje, co je pripravene na odovzdanie do Gitu a co ostava ako externy artefakt mimo repozitara.

Repozitar je pripraveny tak, aby sa dal spustit aj bez plnych datasetov, base modelu a LoRA vah. V Gite maju byt zdrojove kody, konfiguracie, testy, male ukazky dat, runbooky a vysledkove reporty. Velke modelove a datasetove subory sa maju odovzdat separatne alebo znovu vytvorit podla runbookov.

## Download links

Kompletny zoznam odkazov je v `docs/download_links.md`.

Zakladne verejne zdroje:

- Qwen2.5-Coder-7B-Instruct: <https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct>
- Methods2Test: <https://github.com/microsoft/methods2test>
- ML4Refactoring: <https://zenodo.org/records/3547639>
- MaRV Scripts and Dataset: <https://zenodo.org/records/14450098>

V2 LoRA adaptery su projektove artefakty a treba ich odovzdat separatne ako ZIP subory alebo release assets.

ZIP subory z lokalnych adapterov vytvoris:

```bash
python scripts/package_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --output-dir artifacts/adapters
```

## Quick start pre ucitela

V root priecinku projektu:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/evaluation/smoke_eval_metrics.py
```

Tieto prikazy nevyzaduju lokalny Qwen model, plne datasety ani LoRA adaptery. Overuju importy, testy a malu evaluation metrics pipeline na syntetickych prikladoch.

## Co je commitovatelne

- `src/llm_ontology/`: kniznicny kod projektu,
- `scripts/`: spustitelne CLI entrypointy,
- `configs/`: training a evaluation konfiguracie,
- `tests/`: automaticke testy,
- `docs/`: runbooky a projektova dokumentacia,
- `data/samples/`: male ukazky datasetoveho formatu,
- `results/*.md` a `results/*.tex`: male textove reporty z vysledkov.

## Co nie je v Gite

Tieto subory su zamerne mimo repozitara:

- base model `Qwen2.5-Coder-7B-Instruct`,
- plne `data/processed/*.jsonl` datasety,
- training checkpointy,
- LoRA adapter weights `adapter_model.safetensors`,
- evaluation predikcie a per-example metriky.

Aktualne v2 LoRA adaptery maju priblizne 50 MB kazdy. Su relativne male oproti base modelu, ale stale ide o binarne modelove vahy, preto zostavaju mimo bezneho Git commitu.

## Externe artefakty

V2 adaptery pouzite vo finalnej evaluacii:

| Model | Adapter directory |
|---|---|
| `b2_testing_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter` |
| `b2_refactoring_v2` | `/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter` |
| `b1_shared_v2` | `/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter` |

Kazdy adapter directory ma obsahovat minimalne:

```text
adapter_config.json
adapter_model.safetensors
tokenizer_config.json
```

Ak budu adaptery odovzdane separatne, staci ich skopirovat na tieto cesty alebo upravit `adapter_path` v `configs/evaluation/eval_models_v2_only.yaml`.

Kontrola adapterov:

```bash
python scripts/check_v2_adapters.py --models-config configs/evaluation/eval_models_v2_only.yaml
```

## Volitelna reprodukcia v2 evaluacie

Ak su dostupne base model, v2 adaptery a test datasety:

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --limit 50 \
  --output-root evaluation_v2_only \
  --overwrite
```

Finalny vacsi beh s limitom 100 je popisany v `docs/v2_evaluation_runbook.md`. Tento repozitar ho nespusta automaticky.

## Vysledkove reporty

Hlavne textove vystupy pripravene na citanie:

- `results/29.5.md`: suhrn dnesnej prace, pipeline oprav, v2 treningu/evaluacie a analyz,
- `results/current_approaches_ml_report.tex`: LaTeX report k projektu,
- `docs/v2_finetuning_runbook.md`: manualny runbook pre v2 fine-tuning,
- `docs/v2_evaluation_runbook.md`: manualny runbook pre v2 evaluation.

## Minimalny spustitelny rozsah

Bez externych modelov a datasetov je garantovane spustitelne:

```bash
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/evaluation/smoke_eval_metrics.py
```

S externymi adaptermi navyse:

```bash
python scripts/check_v2_adapters.py --models-config configs/evaluation/eval_models_v2_only.yaml
```

S plnym base modelom a datasetmi navyse:

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --limit 5 \
  --output-root evaluation_v2_smoke \
  --overwrite
```
