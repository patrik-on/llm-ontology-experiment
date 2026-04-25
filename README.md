# LLM pre Softvérové Inžinierstvo – Diplomová práca

Experimentálny repozitár pre diplomovú prácu zameranú na využitie veľkých jazykových modelov v softvérovom inžinierstve.

Prvá fáza projektu sa sústredí na **fine-tuning LLM modelov** pre dve domény:

- **refaktoring kódu**
- **generovanie unit testov**

Repozitár je však navrhnutý tak, aby bolo možné neskôr doplniť aj **RAG**, **Split RAG** a **Graph RAG** bez veľkého refaktoringu štruktúry.

---

## Cieľ experimentu

Cieľom je porovnať, či je výhodnejšie použiť:

1. jeden spoločný model trénovaný na viacerých doménach,
2. alebo viacero špecializovaných modelov, kde každý rieši jednu konkrétnu doménu.

V prvej fáze sa rieši iba fine-tuning:

| Konfigurácia | Popis | Stav |
|---|---|---|
| **B1** | Shared Fine-tuning – jeden model trénovaný na refaktoringu aj testovaní | Aktívne |
| **B2-R** | Split Fine-tuning – model špecializovaný na refaktoring | Aktívne |
| **B2-T** | Split Fine-tuning – model špecializovaný na generovanie testov | Aktívne |
| **C0** | Vanilla LLM baseline bez fine-tuningu | Neskôr |
| **A1/A2/A3** | RAG, Split RAG a Graph RAG konfigurácie | Budúce rozšírenie |

---

## Štruktúra repozitára

```text
llm-ontology-experiment/
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
│
├── configs/
│   ├── base.yaml
│   ├── experiments/
│   │   ├── b1_shared_ft.yaml
│   │   ├── b2_refactoring_ft.yaml
│   │   └── b2_testing_ft.yaml
│   └── templates/
│       └── rag_template.yaml
│
├── data/
│   ├── raw/
│   │   ├── methods2test/
│   │   └── marv/
│   │
│   ├── processed/
│   │   ├── refactoring/
│   │   ├── testing/
│   │   └── combined/
│   │
│   └── external/
│
├── src/
│   └── llm_ontology/
│       ├── __init__.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── logging.py
│       │   └── paths.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── download.py
│       │   ├── clean.py
│       │   ├── format.py
│       │   └── split.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base_model.py
│       │   └── adapters.py
│       │
│       ├── training/
│       │   ├── __init__.py
│       │   ├── dataset.py
│       │   ├── trainer.py
│       │   ├── sampler.py
│       │   └── callbacks.py
│       │
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── generate.py
│       │   └── prompts.py
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── metrics.py
│       │   ├── refactoring.py
│       │   ├── testing.py
│       │   └── report.py
│       │
│       └── retrieval/
│           └── __init__.py
│
├── scripts/
│   ├── prepare_data.py
│   ├── train.py
│   ├── generate.py
│   └── evaluate.py
│
├── results/
│   ├── b1_shared_ft/
│   ├── b2_refactoring_ft/
│   └── b2_testing_ft/
│
├── artifacts/
│   ├── adapters/
│   ├── checkpoints/
│   └── indexes/
│
├── docs/
│   ├── experiment_design.md
│   └── finetuning_design.md
│
├── notebooks/
│   ├── 01_dataset_exploration.ipynb
│   └── 02_results_analysis.ipynb
│
└── tests/
    ├── test_config.py
    ├── test_data.py
    ├── test_training.py
    ├── test_generation.py
    └── test_metrics.py