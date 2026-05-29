# scripts/evaluation

CLI skripty pre aktuálnu evaluation pipeline: inference, proxy metriky, agregácie a Markdown report.

Hlavná logika je v `src/llm_ontology/evaluation/`. Evaluation výstupy sa ukladajú pod `evaluation/` a sú lokálne artefakty, nie sú určené na commit.

## Skripty

- `run_inference_eval.py`: spustí generovanie predikcií pre jeden task (`testing` alebo `refactoring`) nad jedným alebo viacerými modelmi z `configs/evaluation/eval_models.yaml`. Vie načítať baseline model aj PEFT LoRA adaptéry, používa zjednotený prompt formatter a zapisuje JSONL predikcie do `evaluation/predictions/<task>/`.
- `compute_eval_metrics.py`: načíta JSONL predikcie a vypočíta per-example aj aggregate metriky. Pre `testing` sleduje napríklad `@Test`, assertions, target-method invocation a trivial test smell. Pre `refactoring` počíta textové a Java-like proxy metriky ako edit similarity, complexity delta, cohesion/coupling proxy a refactoring quality score.
- `build_eval_report.py`: z agregovaných metrík vytvorí Markdown report `evaluation/reports/evaluation_report.md` a kvalitatívne ukážky v `evaluation/samples/`.
- `run_full_evaluation.py`: orchestruje celý tok: inference pre každý model/task, výpočet metrík a report. Každý model spúšťa cez samostatný Python proces, aby sa po modeli uvoľnila VRAM a stav `bitsandbytes/accelerate`.
- `smoke_eval_metrics.py`: vytvorí malé dummy predikcie v `evaluation_smoke/`, spustí metriky a report writer. Slúži na rýchle overenie, že evaluation pipeline zapisuje očakávané súbory bez načítania veľkého modelu.
- `evaluate.py`: legacy vstup pre odstránený `experiment.yaml` flow. Na nové experimenty ho nepoužívaj; iba vypíše navigáciu na aktuálnu pipeline.

## Bežné príkazy

Malý inference pilot:

```bash
python scripts/evaluation/run_inference_eval.py \
  --task testing \
  --models-config configs/evaluation/eval_models.yaml \
  --dataset data/processed/testing/test.jsonl \
  --output evaluation/predictions/testing \
  --limit 5 \
  --model-name baseline_qwen25_coder_7b \
  --overwrite
```

Metriky z existujúcich predikcií:

```bash
python scripts/evaluation/compute_eval_metrics.py \
  --task testing \
  --predictions-dir evaluation/predictions/testing \
  --output-dir evaluation/metrics/testing
```

Celá evaluation s limitom:

```bash
python scripts/evaluation/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models.yaml \
  --limit 100 \
  --output-root evaluation \
  --overwrite
```

Smoke test bez modelu:

```bash
python scripts/evaluation/smoke_eval_metrics.py
```

Proxy metriky sú porovnávacie a škálovateľné, ale nenahrádzajú reálne Java buildy, JaCoCo coverage ani manuálnu kvalitatívnu analýzu.
