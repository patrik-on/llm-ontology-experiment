# LLM pre Softvérové Inžinierstvo – Diplomová práca

Experimentálny repozitár pre porovnanie konfigurácií **fine-tuningu** (a v budúcnosti **RAG**) jazykových modelov na úlohách softvérového inžinierstva – konkrétne **refaktoring kódu** a **generovanie unit testov**.

---

## Prehľad experimentov

| Konfigurácia | Popis | Stav |
|---|---|---|
| **C0** | Baseline – vanilla LLM bez úprav | ✅ Aktívne |
| **B1** | Shared Fine-tuning – jeden model, obe domény | ✅ Aktívne |
| **B2** | Split Fine-tuning – Model-R (refaktoring) + Model-T (testovanie) | ✅ Aktívne |
| **A1** | Shared RAG – jeden vektorový index pre obe domény | 🔜 Budúce |
| **A2** | Split RAG – samostatné indexy + domain router | 🔜 Budúce |
| **A3** | Graph RAG – ontológiami obohatený retrieval (SWO, CodeOntology) | 🔜 Budúce |

---

## Rýchly štart

### 1. Klonovanie repozitára

```bash
git clone https://github.com/<tvoj-username>/llm-se-experiment.git
cd llm-se-experiment
```

### 2. Inštalácia prostredia

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# alebo
.venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Stiahnutie datasetov

```bash
python src/data_preparation/download_datasets.py
```

Stiahne:
- **Methods2Test** (Microsoft) – páry `focal method → JUnit test`
- **MaRV** (Zenodo) – before/after páry refaktoringov z Java repozitárov

### 4. Príprava dát

```bash
python src/data_preparation/cleantest_filters.py    # CleanTest filtre
python src/data_preparation/format_instructions.py  # Inštrukčný formát
python src/data_preparation/split_dataset.py        # Delenie 80/10/10
```

### 5. Tréning

```bash
# B1 – Shared Fine-tuning (jeden model, obe domény)
bash scripts/run_b1_training.sh

# B2 – Split Fine-tuning (Model-R a Model-T zvlášť)
bash scripts/run_b2_training.sh
```

### 6. Hodnotenie

```bash
bash scripts/run_evaluation.sh
```

Výsledky sa uložia do `experiments/<konfigurácia>/results/`.

---

## Hardvérové požiadavky

| Komponent | Minimum | Odporúčané |
|---|---|---|
| GPU VRAM | 10 GB (7B model, QLoRA 4-bit) | 16 GB (aj 13B model) |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB | 200 GB (raw datasety + checkpointy) |

Projekt bol vyvíjaný na **NVIDIA RTX 3080 16 GB** (notebook), Windows 11 + WSL2 / Linux.

---

## Datasety

### Methods2Test
- **Zdroj:** [github.com/microsoft/methods2test](https://github.com/microsoft/methods2test)
- **Obsah:** 780 944 párov Java metóda → JUnit test
- **Čistenie:** CleanTest filtre (syntax, relevance, coverage) – očakávaný úbytok ~43 %
- **Doména:** Generovanie unit testov

### MaRV
- **Zdroj:** [zenodo.org/records/14450098](https://zenodo.org/records/14450098)
- **Obsah:** 693 before/after refaktoringových párov z 126 Java GitHub repozitárov
- **Typy:** Rename Method, Rename Variable, Extract Method, Remove Parameter
- **Doména:** Refaktoring kódu

---

## Konfigurácia modelov

Konfigurácie sú v adresári `configs/`. Základné nastavenia:

```yaml
# configs/finetuning/lora_config.yaml
lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules: [q_proj, v_proj, k_proj, o_proj]

quantization:
  bits: 4          # QLoRA 4-bit

training:
  optimizer: adamw
  learning_rate: 2e-4
  scheduler: cosine
  batch_size: 4
  gradient_accumulation_steps: 4
  epochs: 3
```

---

## Metriky hodnotenia

### Refaktoring (Model-R / B2, alebo B1 na refaktoringových vstupoch)
- **Build success rate** – syntaktická korektnosť výstupu (javac/Maven)
- **Cyclomatic complexity** – pokles = zjednodušenie logiky
- **Cognitive complexity** – čitateľnosť kódu
- **LCOM / TCC** – kohézia triedy (žiaduci rast)
- **CBO, RFC, fan-out** – coupling (žiaduci pokles)
- **F1-score** – zhoda s ground truth refaktoringom

### Testovanie (Model-T / B2, alebo B1 na testovacích vstupoch)
- **Line / Branch / Method coverage** – meria JaCoCo
- **Mutation score** – podiel odhalených mutantov (sila testov)
- **F1-score** – pokrytie očakávaných testovacích scenárov

### Štatistika
- Wilcoxonov párový test pre porovnanie konfigurácií
- 95% intervaly spoľahlivosti

---

## Štruktúra repozitára

```
llm-se-experiment/
├── configs/            # YAML konfigurácie (modely, tréning, RAG)
├── data/               # Surové, spracované a kombinované datasety
├── docs/               # Dokumentácia a popis architektúry
├── experiments/        # Výstupy experimentov (logy, metriky, checkpointy)
├── notebooks/          # Jupyter notebooky pre analýzu a vizualizáciu
├── scripts/            # Shell skripty pre spúšťanie experimentov
├── src/
│   ├── data_preparation/   # Čistenie a formátovanie dát
│   ├── finetuning/         # Tréningový kód (B1, B2)
│   ├── rag/                # [BUDÚCE] RAG vetva (A1, A2, A3)
│   ├── inference/          # Spúšťanie modelov (C0, B1/B2, RAG)
│   └── evaluation/         # Metriky a reporty
└── tests/              # Unit testy zdrojového kódu
```

---

## Roadmap

- [x] Štruktúra repozitára
- [x] Príprava datasetov (Methods2Test + MaRV)
- [ ] Implementácia CleanTest filtrov
- [ ] Tréning B1 (Shared Fine-tuning)
- [ ] Tréning B2 (Split Fine-tuning)
- [ ] Hodnotenie B1, B2, C0
- [ ] RAG vetva A1 (Shared RAG)
- [ ] RAG vetva A2 (Split RAG + router)
- [ ] RAG vetva A3 (Graph RAG + ontológie)
- [ ] Finálne porovnanie všetkých konfigurácií

---

## Licencia

Tento repozitár je určený pre akademické účely v rámci diplomovej práce.
