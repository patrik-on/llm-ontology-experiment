# LLM Ontology Experiment

Experimentálny repozitár pre diplomovú prácu zameranú na využitie veľkých jazykových modelov v softvérovom inžinierstve.

Aktuálna fáza projektu pripravuje datasety, modelové konfigurácie a infraštruktúru pre fine-tuning modelu **Qwen2.5-Coder-7B-Instruct** na dvoch úlohách:

- refaktoring Java kódu,
- generovanie JUnit testov.

Repozitár je zároveň pripravený tak, aby bolo možné neskôr doplniť RAG, Split RAG a Graph RAG experimenty bez zásadnej zmeny štruktúry.

## Experimenty

| Konfigurácia | Popis | Stav |
|---|---|---|
| **B1** | Shared fine-tuning na refaktoringu aj testovaní | Datasety a config pripravené |
| **B2-R** | Fine-tuning iba na refaktoringu | Datasety a config pripravené |
| **B2-T** | Fine-tuning iba na generovaní testov | Datasety a config pripravené |
| **C0** | Ollama baseline bez fine-tuningu | Config a runner pripravené |
| **A1/A2/A3** | RAG, Split RAG, Graph RAG | Budúce rozšírenie |

Plný fine-tuning sa zatiaľ nespúšťa. Aktuálne sú pripravené iba dáta, konfigurácie, validačné skripty a skeleton loaderov.

## Datasety

Spracované datasety sú uložené v `data/processed/`.

| Dataset | Úloha | Split-y | Poznámka |
|---|---|---|---|
| `testing/` | JUnit test generation | `4000/500/500` | Methods2Test |
| `refactoring_marv/` | Refactoring | `478/100/108` | MaRV |
| `refactoring_ml4ref/` | Refactoring | `4000/500/500` | ML4Refactoring subset |
| `refactoring/` | B2-R final | `4478/600/608` | ML4Refactoring + MaRV |
| `combined/` | B1 final | `8000/1000/1000` | Methods2Test + ML4Refactoring, bez MaRV |

JSONL záznamy sú v instruction-tuning formáte a obsahujú minimálne:

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "domain": "refactoring alebo testing",
  "source": "..."
}
```

### ML4Refactoring

ML4Refactoring dataset je očakávaný mimo repozitára:

```text
C:/datasets/ml4refactoring/all/dataset/
```

Pipeline spracúva projektové ZIPy po jednom, rozbaľuje ich do dočasného priečinka, páruje `before-refactoring` a `after-refactoring` súbory podľa relatívnej cesty a ignoruje `-astc` súbory.

Užitočné príkazy:

```powershell
py scripts/inspect_ml4refactoring.py --project-zip C:/datasets/ml4refactoring/all/dataset/apache-abdera.zip
py scripts/prepare_ml4refactoring.py
py scripts/prepare_final_datasets.py
```

## Modely

Používané modely sú definované v `configs/models/`.

| Model | Config | Účel |
|---|---|---|
| Hugging Face Qwen2.5-Coder-7B-Instruct | `configs/models/qwen25_coder_7b_hf.yaml` | LoRA/QLoRA fine-tuning |
| Ollama `qwen2.5-coder:7b` | `configs/models/qwen25_coder_7b_ollama.yaml` | Lokálna baseline inferencia |

Lokálny Hugging Face model sa očakáva mimo repozitára:

```text
C:/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

Modelové váhy, checkpointy a logy sa necommitujú.

## Fine-Tuning Konfigurácie

Fine-tuning konfigurácie sú v `configs/finetuning/`:

- `lora_config.yaml`
- `training_b1_shared.yaml`
- `training_b2_refactoring.yaml`
- `training_b2_testing.yaml`

Všetky tréningové configy sú zatiaľ nastavené ako dry-run:

```yaml
run:
  dry_run: true
  max_train_samples: 50
  max_val_samples: 20
  max_steps: 5
  seed: 42
```

LoRA/QLoRA skeleton je implementovaný v:

```text
src/llm_ontology/finetuning/
├── dataset_loader.py
├── model_loader.py
└── prompt_formatter.py
```

Prompt formát:

```text
### Instruction:
...

### Input:
...

### Response:
...
```

## Ollama Baseline

Baseline konfigurácia je v:

```text
configs/inference/ollama_qwen25_coder_baseline.yaml
```

Runner je pripravený v:

```powershell
py scripts/run_ollama_baseline.py
```

Defaultne generuje najviac 20 predikcií na dataset. Skript nie je spúšťaný automaticky a neslúži na fine-tuning.

## Kontroly Setupu

Overenie modelového setupu:

```powershell
py scripts/check_model_setup.py
```

Skript kontroluje:

- HF model config,
- lokálny HF model priečinok,
- `config.json`,
- tokenizer config,
- `.safetensors` súbory,
- Ollama API,
- dostupnosť modelu `qwen2.5-coder:7b`.

Overenie fine-tuning infraštruktúry:

```powershell
py scripts/check_finetuning_setup.py
```

Skript kontroluje:

- tréningové configy,
- dataset súbory,
- prvý validný JSONL záznam v každom splite,
- prompt formatter,
- experiment priečinky.

## Štruktúra Repozitára

```text
llm-ontology-experiment/
├── configs/
│   ├── datasets/
│   ├── experiments/
│   ├── finetuning/
│   ├── inference/
│   ├── models/
│   └── templates/
├── data/
│   ├── raw/
│   ├── processed/
│   │   ├── combined/
│   │   ├── refactoring/
│   │   ├── refactoring_marv/
│   │   ├── refactoring_ml4ref/
│   │   └── testing/
│   └── external/
├── experiments/
│   ├── b1_shared/
│   ├── b2_refactoring/
│   ├── b2_testing/
│   └── c0_ollama_baseline/
├── scripts/
│   ├── check_finetuning_setup.py
│   ├── check_model_setup.py
│   ├── inspect_ml4refactoring.py
│   ├── prepare_final_datasets.py
│   ├── prepare_ml4refactoring.py
│   └── run_ollama_baseline.py
└── src/
    └── llm_ontology/
        ├── core/
        ├── data/
        ├── evaluation/
        ├── finetuning/
        ├── inference/
        ├── models/
        ├── retrieval/
        └── training/
```

## Inštalácia

Základné závislosti:

```powershell
pip install -r requirements.txt
```

Fine-tuning závislosti zahŕňajú `transformers`, `datasets`, `peft`, `accelerate`, `torch` a podľa platformy `bitsandbytes`. Na Windows môže byť 4-bit QLoRA cez `bitsandbytes` limitovaná; pre reálny tréning je vhodnejšie Linux/CUDA prostredie.

## Bezpečnostné Poznámky

- Necommitovať `C:/models/` ani žiadne modelové váhy.
- Necommitovať checkpointy a logy z `experiments/**/checkpoints/` a `experiments/**/logs/`.
- Nespúšťať plný fine-tuning bez samostatnej kontroly GPU prostredia.
- Ollama baseline používa iba lokálnu inferenciu, nie tréning.
