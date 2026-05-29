# LLM Ontology Experiment

Repozitár pre diplomovú prácu zameranú na použitie veľkých jazykových modelov pri úlohách softvérového inžinierstva. Projekt aktuálne rieši dve hlavné úlohy:

- generovanie JUnit testov pre Java metódy,
- refaktoring Java kódu.

Hlavný lokálny model je **Qwen2.5-Coder-7B-Instruct**. Fine-tuning prebieha cez Hugging Face Transformers, PEFT a LoRA/QLoRA. Ollama model `qwen2.5-coder:7b` slúži iba ako baseline/prompt testing, nie na fine-tuning.

## Aktuálny Stav

| Oblasť | Verzia / stav | Poznámka |
|---|---:|---|
| Dokumentácia | 2026-05-08 | README aktualizované podľa aktuálnej štruktúry projektu |
| Dataset pipeline | v1 | Methods2Test, MaRV, ML4Refactoring a finálne mixy pripravené |
| Fine-tuning pipeline | v2 | QLoRA, early stopping, resume z checkpointu, robustné summary pri chybe/Ctrl+C |
| WSL setup | v1 | Reálne tréningy používajú WSL2/CUDA; výstupy idú mimo OneDrive |
| Evaluation pipeline | v1 | Inference, proxy metriky, CSV/JSON/Markdown reporty |
| RAG experimenty | plán | Zatiaľ len šablóna, nie implementácia |

## Reprodukovateľný Handoff

Repozitár je pripravený tak, aby bol spustiteľný aj bez plných datasetov, base modelu a LoRA váh. Minimálna kontrola pre učiteľa:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src scripts tests
python -m pytest tests
python scripts/evaluation/smoke_eval_metrics.py
```

Tieto príkazy overia zdrojový kód, testy a malú evaluation metrics pipeline na syntetických príkladoch. Kompletný handoff popis je v `docs/reproducible_handoff.md`.

Modelové váhy, plné datasety a v2 LoRA adaptéry nie sú súčasťou Git repozitára. V2 adaptéry majú približne 50 MB každý a majú byť odovzdané separatne alebo uložené na cestách uvedených v `configs/evaluation/eval_models_v2_only.yaml`. Ich prítomnosť sa dá overiť:

```bash
python scripts/check_v2_adapters.py --models-config configs/evaluation/eval_models_v2_only.yaml
```

## Ciele Projektu

1. Pripraviť datasety pre instruction-tuning na test generation a refactoring.
2. Natrénovať a porovnať tri LoRA/QLoRA varianty:
   - **B2-T**: testing-only fine-tuning,
   - **B2-R**: refactoring-only fine-tuning,
   - **B1**: shared fine-tuning na oboch úlohách.
3. Porovnať baseline a fine-tuned modely na testovacej a refaktoringovej úlohe.
4. Vytvoriť auditovateľné výstupy použiteľné v diplomovej práci: JSONL predikcie, CSV metriky, agregácie a Markdown report.
5. Neskôr rozšíriť projekt o RAG / Split RAG / Graph RAG experimenty.

## Experimenty

| Experiment | Úloha | Model / adaptér | Stav |
|---|---|---|---|
| **C0** | baseline inference | Qwen2.5-Coder-7B-Instruct bez adaptéra alebo Ollama baseline | infra pripravená |
| **B2-T** | JUnit test generation | LoRA adaptér v `experiments/b2_testing/checkpoints/final_adapter` | prvý beh dokončený/prerušený po cca 1 epoche, adaptér dostupný |
| **B2-R** | refactoring | LoRA adaptér v `experiments/b2_refactoring/checkpoints/final_adapter` | prvý beh prerušený po checkpoint-300, adaptér dostupný |
| **B1** | shared testing + refactoring | LoRA adaptér v `/home/patrik/experiments/llm-ontology/b1_shared/checkpoints/final_adapter` | WSL výstup mimo repozitára |
| **A1/A2/A3** | RAG varianty | zatiaľ bez modelovej implementácie | plánované |

## Datasety

Spracované datasety sú v `data/processed/`.

| Dataset | Úloha | Train | Val | Test | Zdroj |
|---|---:|---:|---:|---:|---|
| `testing/` | JUnit test generation | 4000 | 500 | 500 | Methods2Test |
| `refactoring_marv/` | refactoring | 478 | 100 | 108 | MaRV |
| `refactoring_ml4ref/` | refactoring | 4000 | 500 | 500 | ML4Refactoring subset |
| `refactoring/` | B2-R final | 4478 | 600 | 608 | ML4Refactoring + MaRV |
| `combined/` | B1 final | 8000 | 1000 | 1000 | Methods2Test + ML4Refactoring |

JSONL záznamy používajú instruction-tuning formát:

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "domain": "testing alebo refactoring",
  "source": "methods2test / marv / ml4refactoring"
}
```

Malé commitovateľné ukážky záznamov sú v `data/samples/`, keďže plné JSONL datasety sú ignorované Gitom.

## Modely A Tréning

Hugging Face model pre WSL:

```text
/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

Windows cesta toho istého lokálneho modelu:

```text
C:/models/huggingface/Qwen2.5-Coder-7B-Instruct
```

Hlavné configy:

- `configs/models/qwen25_coder_7b_hf_wsl.yaml`
- `configs/finetuning/lora_config.yaml`
- `configs/finetuning/training_b2_testing_wsl.yaml`
- `configs/finetuning/training_b2_refactoring_wsl.yaml`
- `configs/finetuning/training_b1_shared_wsl.yaml`

Hlavná tréningová logika je v `src/llm_ontology/training/finetuning.py`. Skript `scripts/training/train_finetuning.py` je iba CLI wrapper, aby zostali zachované pôvodné príkazy.

Rovnaký princíp platí aj pre evaluation: `scripts/` obsahuje spustiteľné vstupy, zatiaľ čo hlavná logika je v `src/llm_ontology/evaluation/`.

Aktuálne QLoRA nastavenie:

- 4-bit NF4 quantization,
- LoRA `r=16`, `alpha=32`, `dropout=0.05`,
- max 2 epochy,
- eval/save každých 100 krokov,
- `load_best_model_at_end=true`,
- early stopping patience 2,
- experiment výstupy vo WSL filesysteme: `/home/patrik/experiments/llm-ontology`.

## Dôležité Príkazy

Kontrola WSL fine-tuning kompatibility:

```bash
python scripts/training/check_transformers_compat.py
python scripts/training/check_finetuning_ready.py --config configs/finetuning/training_b1_shared_wsl.yaml
```

Spustenie tréningu:

```bash
python scripts/training/train_finetuning.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/training/train_finetuning.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
python scripts/training/train_finetuning.py --config configs/finetuning/training_b1_shared_wsl.yaml
```

Pokračovanie z checkpointu:

```bash
python scripts/training/train_finetuning.py \
  --config configs/finetuning/training_b1_shared_wsl.yaml \
  --resume_from_checkpoint /home/patrik/experiments/llm-ontology/b1_shared/checkpoints/checkpoint-300
```

Malá evaluation inference:

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

Full evaluation s limitom 100:

```bash
python scripts/evaluation/run_full_evaluation.py \
  --models-config configs/evaluation/eval_models.yaml \
  --limit 100 \
  --output-root evaluation \
  --overwrite
```

`run_full_evaluation.py` spúšťa každý model v samostatnom Python procese, aby sa po každom modeli uvoľnila VRAM a bitsandbytes/accelerate stav.

## Developer Setup

Základné vývojové prostredie:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q src scripts tests
```

WSL/CUDA prostredie pre reálny fine-tuning:

```bash
python -m pip install -e ".[dev,training]"
python scripts/training/check_transformers_compat.py
```

`training` extra obsahuje aj Linux/WSL-only `bitsandbytes`. Na natívnom Windows sa QLoRA stále odporúča spúšťať vo WSL2.

## Evaluation Pipeline

Evaluation výstupy sú v `evaluation/`:

- `predictions/`: JSONL predikcie po modeli a úlohe,
- `metrics/`: per-example a aggregate metriky v JSON/CSV,
- `reports/`: Markdown report,
- `samples/`: kvalitatívne ukážky.

Testing metriky obsahujú proxy pre test coverage a test quality:

- výskyt `@Test`,
- počet testovacích metód,
- assertion/verify count,
- trivial test smell,
- coverage proxy score.

Refactoring metriky obsahujú proxy pre:

- code health,
- cohesion,
- coupling,
- podobnosť k referenčnému výstupu.

Tieto metriky sú textové/proxy metriky. Nenahrádzajú reálne JaCoCo coverage, kompiláciu ani manuálne hodnotenie.

## Kalendár Práce

| Dátum / fáza | Stav | Úloha |
|---|---|---|
| 2026-02 | splnené | Založenie projektu, základná štruktúra, prvé dataset skripty |
| 2026-03 | splnené | Spracovanie Methods2Test a MaRV datasetov |
| 2026-04 | splnené | ML4Refactoring pipeline a subset 4000/500/500 |
| 2026-04 | splnené | Finálne datasety `refactoring/` a `combined/` |
| 2026-05 | splnené | Hugging Face/Ollama configy, prompt formatter, model/dataset loadery |
| 2026-05 | splnené | WSL QLoRA setup, readiness checks, compatibility fixes pre Transformers |
| 2026-05 | splnené | Robustný training script: summary, Ctrl+C, failed runs, resume checkpoint |
| 2026-05 | splnené | Early stopping a presun WSL experiment outputov mimo OneDrive |
| 2026-05 | splnené | Evaluation pipeline, proxy metriky a Markdown report |
| 2026-05 | splnené | Full evaluation upravená tak, aby každý model bežal v samostatnom procese |
| najbližšie | plánované | Spustiť stabilnú full evaluation s väčším limitom |
| najbližšie | plánované | Vyhodnotiť B1/B2-T/B2-R v tabuľkách pre diplomovku |
| ďalšia fáza | plánované | Kvalitatívna analýza vybraných predikcií |
| ďalšia fáza | plánované | Prípadný spustiteľný Java subset pre reálne coverage meranie |
| neskôr | plánované | RAG / Split RAG / Graph RAG porovnanie |

## Orientácia V Repozitári

Hlavné priečinky majú vlastný `info.md` s krátkym vysvetlením. Rýchla mapa:

| Priečinok | Obsah |
|---|---|
| `configs/` | YAML konfigurácie modelov, tréningu, inferencie a evaluation |
| `data/` | raw a processed datasety |
| `docs/` | detailnejšia dokumentácia a poznámky k WSL/fine-tuningu |
| `evaluation/` | predikcie, metriky, reporty a ukážky |
| `experiments/` | lokálne checkpointy/adaptéry a tréningové výsledky v repo časti |
| `scripts/` | spustiteľné CLI skripty pre dáta, tréning, inferenciu a evaluation |
| `src/llm_ontology/` | knižničný Python kód projektu; obsahuje reálnu logiku pre data, training, inference a evaluation |
| `tests/` | testy a budúce overovanie |
| `notebooks/` | experimentálne notebooky |
| `artifacts/` a `results/` | pomocné výstupy a staršie výsledky |

## Bezpečnostné A Praktické Poznámky

- Necommitovať modelové váhy: `*.safetensors`, `*.bin`, `*.pt`, `*.gguf`.
- Necommitovať veľké checkpointy a logy.
- Detailné pravidlá, čo commitovať a čo ignorovať, sú v `docs/git_commit_policy.md`.
- WSL tréningové výstupy ukladať mimo OneDrive do `/home/patrik/experiments/llm-ontology`.
- Fine-tuning používa Hugging Face + PEFT, nie Ollama.
- Natívny Windows nie je odporúčaný pre QLoRA, pretože `bitsandbytes` môže byť problematický.
- Evaluation s viacerými modelmi má bežať cez `run_full_evaluation.py`, ktorý izoluje modely do samostatných procesov.

