# Evaluation artifacts

Všetky lokálne evaluation výstupy patria výhradne pod:

```text
artifacts/evaluation/runs/<run_id>/
├── run_manifest.json
├── predictions/
├── metrics/
├── reports/
├── samples/
└── analysis/
```

`run_id` je stabilný názov experimentu, nie ľubovoľná cesta. Runner akceptuje
iba malé písmená, čísla, `.`, `_` a `-`; tým nemôže vytvárať nové evaluation
priečinky v koreni repozitára. Opakovaný beh rovnakého experimentu používa
rovnaký `run_id` a vyžaduje explicitné `--overwrite` na prepísanie predikcií.

Historická migrácia:

| Pôvodný priečinok | Canonical run_id | Význam |
|---|---|---|
| `evaluation/` | `legacy_v1_full` | pôvodná 30-príkladová matica |
| `evaluation_smoke/` | `metrics_smoke` | model-free pipeline smoke |
| `evaluation_v2/` | `v1_v2_pilot` | 5-príkladové V1/V2 porovnanie |
| `evaluation_v2_only/` | `v2_final` | 50-príkladová V2 evaluácia a analýzy |
| `evaluation_v2_only_smoke/` | `v2_final_smoke` | 2-príkladový V2 smoke |

Obsah `runs/` je odvodený a ignorovaný Gitom. Tento `info.md`, kód kontraktu a
runbooky sú verziované.
