# V2 evaluation runbook

## Purpose

Tento runbook pripravuje evaluáciu v2 adaptérov po oprave prompt masking pipeline. Cieľom je porovnať baseline, v1/pilotné adaptéry a nové v2 adaptéry na rovnakých testing/refactoring test splitoch.

Veľkú evaluáciu spúšťa používateľ manuálne. Tento dokument obsahuje príkazy, kontroly a očakávané výstupy.

## Compared models

Config: `configs/evaluation/eval_models.yaml`

- `baseline_qwen25_coder_7b`: baseline bez LoRA adaptéra.
- `b2_testing_v1`: v1 testing-only adaptér.
- `b2_refactoring_v1`: v1 refactoring-only adaptér.
- `b1_shared_v1`: v1 shared adaptér.
- `b2_testing_v2`: v2 testing-only adaptér.
- `b2_refactoring_v2`: v2 refactoring-only adaptér.
- `b1_shared_v2`: v2 shared adaptér.

## V2 adapter paths

```text
/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter
/home/patrik/experiments/llm-ontology-v2/b2_refactoring/checkpoints/final_adapter
/home/patrik/experiments/llm-ontology-v2/b1_shared/checkpoints/final_adapter
```

Každý v2 adaptér má obsahovať:

- `adapter_config.json`
- `adapter_model.safetensors`
- `tokenizer_config.json`

## Environment

Spúšťaj vo WSL v koreňovom priečinku projektu:

```bash
cd /mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment
source .venv_wsl/bin/activate
```

## Pre-flight checks

```bash
python -m compileall -q src scripts tests
python scripts/check_v2_adapters.py
python scripts/run_full_evaluation.py --help
```

Voliteľne môžeš pred smoke behom skontrolovať model list:

```bash
python - <<'PY'
from llm_ontology.core.config import read_yaml
cfg = read_yaml("configs/evaluation/eval_models.yaml")
for model in cfg["models"]:
    print(model["name"], "->", model.get("adapter_path") or "baseline")
PY
```

## Smoke eval limit 5

Malý smoke beh overí načítanie modelov, adaptérov, generovanie predikcií, metriky a report writer. Spúšťa všetky modely v configu, preto aj limit 5 môže chvíľu trvať.

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models.yaml \
  --limit 5 \
  --output-root evaluation_v2 \
  --overwrite
```

## Final eval limit 100

Finálny porovnávací beh s limitom 100 spusti až po úspešnom smoke behu.

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models.yaml \
  --limit 100 \
  --output-root evaluation_v2 \
  --overwrite
```

`run_full_evaluation.py` spúšťa každý model v samostatnom subprocess-e. Je to zámerné, aby sa medzi modelmi uvoľnila GPU pamäť a stav knižníc `bitsandbytes`/`accelerate`.

## Check aggregate metrics

```bash
cat evaluation_v2/metrics/testing/aggregate_metrics.json
cat evaluation_v2/metrics/refactoring/aggregate_metrics.json
cat evaluation_v2/reports/evaluation_report.md
```

CSV tabuľky sú v:

```text
evaluation_v2/metrics/testing/aggregate_metrics.csv
evaluation_v2/metrics/refactoring/aggregate_metrics.csv
```

## Save limit100 reports

Po dokončení finálneho limit 100 behu ulož reporty s názvom `limit100`, aby sa nepoplietli so smoke výstupmi:

```bash
mkdir -p evaluation_v2/reports/limit100
cp evaluation_v2/reports/evaluation_report.md evaluation_v2/reports/limit100/evaluation_report_limit100.md
cp evaluation_v2/metrics/testing/aggregate_metrics.json evaluation_v2/reports/limit100/testing_aggregate_metrics_limit100.json
cp evaluation_v2/metrics/refactoring/aggregate_metrics.json evaluation_v2/reports/limit100/refactoring_aggregate_metrics_limit100.json
cp evaluation_v2/metrics/testing/aggregate_metrics.csv evaluation_v2/reports/limit100/testing_aggregate_metrics_limit100.csv
cp evaluation_v2/metrics/refactoring/aggregate_metrics.csv evaluation_v2/reports/limit100/refactoring_aggregate_metrics_limit100.csv
```

## Notes

- Nespúšťaj fine-tuning počas evaluation prípravy.
- Nemeň datasety medzi v1/v2 porovnaním.
- V2 adaptéry sú len pridané ako nové modely; v1 adaptéry ostávajú dostupné pre porovnanie.
- `evaluation_v2/` je lokálny výstupný priečinok a nemá sa commitovať ako veľký artefakt.
