# scripts

CLI vstupy projektu. Skripty v tomto priečinku sú určené na spúšťanie konkrétnych krokov pipeline z príkazového riadku. Hlavná implementačná logika má zostať v `src/llm_ontology/`; skripty majú byť tenké wrappery, ktoré nastavujú `PYTHONPATH`, parsujú argumenty a volajú knižničné funkcie.

## Základné pravidlo

Ak meníš správanie projektu, uprednostni úpravu kódu v `src/llm_ontology/`. Skript upravuj najmä vtedy, keď pridávaš alebo spresňuješ CLI argumenty, smoke check, debug výpis alebo spätnú kompatibilitu pre starý príkaz.

## Priečinky

- `data/`: kontrola raw datasetov, príprava datasetov a tvorba finálnych B1/B2 JSONL splitov.
- `training/`: kontroly WSL/CUDA prostredia, prompt masking debug a LoRA/QLoRA fine-tuning.
- `evaluation/`: inference nad baseline/LoRA modelmi, výpočet metrík, Markdown report a smoke evaluation.
- `inference/`: staršie alebo samostatné inference vstupy mimo hlavnej evaluation pipeline, najmä Ollama baseline.

## Odporúčaný tok práce

1. Príprava dát:

```bash
python scripts/data/prepare_methods2test.py
python scripts/data/prepare_ml4refactoring.py
python scripts/data/prepare_marv.py
python scripts/data/prepare_final_datasets.py
```

2. Kontrola tréningového prostredia vo WSL:

```bash
python scripts/training/check_transformers_compat.py
python scripts/training/check_finetuning_ready.py --config configs/finetuning/training_b1_shared_wsl.yaml
python scripts/training/debug_prompt_masking.py
```

3. Krátky bezpečný dry-run pred reálnym tréningom:

```bash
python scripts/training/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --dry-run \
  --max_steps 2 \
  --max_train_samples 4 \
  --max_val_samples 2 \
  --output-root /tmp/llm-ontology-dry-run
```

4. Evaluation:

```bash
python scripts/evaluation/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models.yaml \
  --limit 100 \
  --output-root evaluation \
  --overwrite
```

## Presunutá logika

- `src/llm_ontology/data/`: dataset pipeline, validácia záznamov, splitovanie a finálne B1/B2 mixy.
- `src/llm_ontology/training/`: QLoRA training engine, readiness checks, prompt masking a summary výstupy.
- `src/llm_ontology/finetuning/`: prompt formatter, dataset loader a model loader.
- `src/llm_ontology/evaluation/`: HF baseline/LoRA inference, proxy metriky, CSV/JSON výstupy a report writer.
- `src/llm_ontology/inference/`: Ollama client a staršie inference helpery.

## Legacy vstupy

Niektoré skripty ostali iba preto, aby staré príkazy zlyhali s jasnou navigáciou na aktuálnu pipeline:

- `scripts/inference/generate.py`
- `scripts/evaluation/evaluate.py`

Nepoužívaj ich na nové experimenty.

