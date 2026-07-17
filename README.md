# LLM Ontology Experiment

Experimentálny repozitár pre diplomovú prácu zameranú na použitie lokálnych
jazykových modelov pri úlohách softvérového inžinierstva. Projekt skúma dve
úlohy nad Java kódom:

- generovanie JUnit testov,
- refaktoring zdrojového kódu.

Hlavným modelom je **Qwen2.5-Coder-7B-Instruct**. Repozitár obsahuje dátovú
pipeline, LoRA/QLoRA fine-tuning, inferenciu, automatické metriky, reportovanie
a pripravenú architektúru pre porovnanie direct LLM, RAG a multi-RAG.

## Aktuálny stav

Aktualizované: **2026-07-17**

| Oblasť | Stav | Poznámka |
|---|---|---|
| Dataset pipeline | hotová | Methods2Test, MaRV, ML4Refactoring a finálne mixy |
| Fine-tuning pipeline | hotová | QLoRA, masking, early stopping, resume, summary |
| Baseline a LoRA inference | hotová | Hugging Face a voliteľný Ollama baseline |
| Evaluation pipeline | hotová | JSONL, CSV, JSON, Markdown a proxy metriky |
| Generation approaches | pripravená architektúra | `direct`, `rag`, `multi_rag` |
| Direct approach | pripravený | zachováva existujúci promptovací formát |
| RAG | návrh/kontrakty | reálne indexovanie ešte nie je implementované |
| Multi-RAG | návrh/kontrakty | routing a fusion ešte nie sú implementované |
| Executable Java evaluation | plán | kompilácia, test execution a JaCoCo subset |

RAG configy sú zámerne `enabled: false`. Repozitár neoznačuje retrieval za
hotový, kým nebude existovať train-only corpus builder, index a retrieval runner.

## Architektonický model

Experiment oddeľuje tri nezávislé osi:

```text
model variant × generation approach × task
```

Príklady:

```text
baseline_qwen25_coder_7b × direct × testing
baseline_qwen25_coder_7b × rag × testing
b2_testing_v2 × rag × testing
baseline_qwen25_coder_7b × multi_rag × refactoring
```

- **Model variant** určuje base model alebo LoRA adaptér.
- **Generation approach** určuje direct prompt, RAG alebo multi-RAG kontext.
- **Task** určuje testing alebo refactoring.

Fine-tuning nie je generation approach: mení váhy modelu. RAG mení vstupný
kontext. Toto oddelenie umožňuje kombinovať fine-tuned model s RAG bez
duplikovania dátovej, inferenčnej alebo evaluation pipeline.

Detailný popis je v [`docs/architecture.md`](docs/architecture.md).

## Rýchla kontrola repozitára

Kontrola nevyžaduje modelové váhy, plné datasety ani CUDA:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts tests
python -m pytest -q
python scripts/evaluation/smoke_eval_metrics.py
```

Smoke evaluation vytvorí dočasný ignorovaný priečinok `evaluation_smoke/`.

## Štruktúra repozitára

```text
configs/                    YAML konfigurácie
├── models/                 Windows, WSL a Ollama modelové configy
├── finetuning/             LoRA/QLoRA training configy
├── experiments/            direct, RAG a multi-RAG experimenty
├── retrieval/              spoločné retrieval nastavenia
├── evaluation/             evaluation modely a datasety
└── datasets/               datasetové nastavenia

src/llm_ontology/
├── core/                   config, cesty a logging
├── data/                   dataset pipeline
├── models/                 model, tokenizer, quantization a LoRA loading
├── training/               fine-tuning engine
├── inference/              prompting a inferenčné helpery
├── approaches/             direct, RAG a multi-RAG prompt composition
├── retrieval/              budúce indexovanie a vyhľadávanie
└── evaluation/             inference, metriky a reportovanie

scripts/                    tenké CLI entrypointy
tests/                      automatizované testy
data/samples/               malé commitovateľné dataset ukážky
docs/                       architektúra a runbooky
artifacts/                  malé manifesty; nie modelové váhy
```

## Datasety

Spracované datasety používajú instruction-tuning JSONL formát:

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "domain": "testing alebo refactoring",
  "source": "methods2test / ml4refactoring / marv"
}
```

| Dataset | Úloha | Train | Val | Test | Zdroj |
|---|---:|---:|---:|---:|---|
| `testing/` | JUnit test generation | 4000 | 500 | 500 | Methods2Test |
| `refactoring_marv/` | refactoring | 478 | 100 | 108 | MaRV |
| `refactoring_ml4ref/` | refactoring | 4000 | 500 | 500 | ML4Refactoring |
| `refactoring/` | B2-R final | 4478 | 600 | 608 | ML4Refactoring + MaRV |
| `combined/` | B1 final | 8000 | 1000 | 1000 | Methods2Test + ML4Refactoring |

Plné datasety sú lokálne v `data/processed/` a nie sú commitované. Malé ukážky
sú v [`data/samples/`](data/samples/README.md).

### Dôležité pravidlo pre RAG

Evaluation index smie obsahovať iba `train` splity. Val slúži na ladenie a test
split sa nesmie indexovať. Pred reálnym RAG experimentom treba navyše vykonať
deduplikáciu a group-split audit podľa projektu a commitu.

## Modely

Modelové konfigurácie:

- `configs/models/qwen25_coder_7b_hf.yaml` – natívny Windows,
- `configs/models/qwen25_coder_7b_hf_wsl.yaml` – WSL cesta,
- `configs/models/qwen25_coder_7b_ollama.yaml` – Ollama baseline.

Očakávaná WSL cesta modelu:

```text
/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

Fine-tuning používa Hugging Face Transformers, PEFT a QLoRA. Ollama slúži iba
na rýchly baseline alebo prompt testing.

## Fine-tuning experimenty

| Model | Tréning |
|---|---|
| `b2_testing_v2` | testing-only |
| `b2_refactoring_v2` | refactoring-only |
| `b1_shared_v2` | testing + refactoring |

Pre-flight kontrola vo WSL:

```bash
python scripts/training/check_transformers_compat.py
python scripts/training/debug_prompt_masking.py
python scripts/check_finetuning_ready.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml
```

Spustenie tréningu:

```bash
python scripts/train_finetuning.py \
  --config configs/finetuning/training_b2_testing_wsl.yaml \
  --output-root /home/patrik/experiments/llm-ontology-v2/b2_testing
```

Detaily sú v [`docs/v2_finetuning_runbook.md`](docs/v2_finetuning_runbook.md).

## Evaluation

Malý inference beh:

```bash
python scripts/run_inference_eval.py \
  --task testing \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --dataset data/processed/testing/test.jsonl \
  --output evaluation/predictions/testing \
  --model-name baseline_qwen25_coder_7b \
  --limit 5 \
  --overwrite
```

Celý evaluation tok:

```bash
python scripts/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml \
  --limit 50 \
  --output-root evaluation_v2_only \
  --overwrite
```

Výstupy:

- `predictions/`: JSONL predikcie,
- `metrics/`: per-example a aggregate JSON/CSV,
- `reports/`: Markdown report,
- `samples/`: kvalitatívne ukážky.

Aktuálne testing a refactoring metriky sú proxy metriky. Nenahrádzajú Java
kompiláciu, test execution, JaCoCo coverage ani overenie behavior preservation.

## Direct, RAG a multi-RAG

Approach kontrakty sú v `src/llm_ontology/approaches/`:

- `direct`: neprijíma retrieval kontext,
- `rag`: vyžaduje aspoň jeden auditovateľný kontext,
- `multi_rag`: kontexty zoskupuje podľa retrieval zdroja.

Každý retrieval context má ID dokumentu, zdroj, voliteľné score a metadata.
Prompt explicitne označuje retrieval obsah ako nedôveryhodný referenčný materiál,
aby sa znížilo riziko prompt injection z indexovaných dokumentov.

Najbližšia implementačná fáza:

1. dataset fingerprinty a leakage audit,
2. train-only corpus builder,
3. embeddings a lokálny index,
4. jednotný RAG retriever,
5. multi-RAG routing a fusion,
6. retrieval a efficiency metriky.

## Externé artefakty

Modelové váhy, checkpointy, plné datasety a adapter ZIP súbory zostávajú mimo
bežného Git repozitára. Malé manifesty a SHA-256 checksumy môžu byť commitované.

Kontrola adapterov:

```bash
python scripts/check_v2_adapters.py \
  --models-config configs/evaluation/eval_models_v2_only.yaml
```

Download odkazy a handoff sú v:

- [`docs/download_links.md`](docs/download_links.md),
- [`docs/reproducible_handoff.md`](docs/reproducible_handoff.md).

## Vývojové pravidlá

- Implementačná logika patrí do `src/llm_ontology/`.
- `scripts/` obsahuje iba tenké CLI wrappery.
- Nový modelový kód importuje z `llm_ontology.models`.
- Nové promptovanie importuje z `llm_ontology.inference.prompting`.
- RAG konfigurácia nesmie predstierať hotový experiment bez indexu a runnera.
- Veľké datasety, modely, checkpointy, predikcie a indexy sa necommitujú.

Pred odovzdaním znovu spusti:

```bash
python -m compileall -q src scripts tests
python -m pytest -q
python scripts/evaluation/smoke_eval_metrics.py
```
