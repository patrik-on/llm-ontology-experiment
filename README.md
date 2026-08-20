# LLM Ontology Experiment

Experimentálny repozitár porovnáva lokálne jazykové modely pri dvoch úlohách
nad Java kódom: generovanie JUnit testov a refaktoring. Aktuálny baseline
porovnáva tri režimy pri rovnakom modeli, prompt contracte a evaluácii:

- **Direct LLM** (`no_rag`) bez retrievalu,
- **RAG** (`single_collection_rag`) nad kolekciou `mixed`,
- **MultiRAG** (`multi_collection_rag`) nad oddelenými kolekciami s RRF.

Ontológia, GraphRAG, router, reranker a literárna kolekcia nie sú súčasťou
aktuálneho baseline.

## Repository Structure

Strom ukazuje výskumne dôležité hranice, nie každý implementačný súbor:

```text
llm-ontology-experiment/
│
├── configs/                         # Verziované nastavenia projektu
│   ├── shared/                      # Spoločné modely, runtime lock a base config
│   ├── datasets/                    # Dataset manifesty a spracovanie
│   ├── finetuning/                  # LoRA/QLoRA tréningové konfigurácie
│   ├── retrieval/                   # Ollama embeddings, Chroma, RAG a MultiRAG
│   ├── inference/                   # Samostatné inference nastavenia
│   ├── evaluation/                  # Modelové matice a evaluation runs
│   ├── experiments/                 # Direct/RAG/MultiRAG experiment cells
│   ├── benchmarks/                  # TestBench a SWE-Refactor nastavenia
│   └── ui/                          # Gradio composition a defaults
│
├── src/llm_ontology/                # Hlavný Python source code
│   ├── core/                        # Config, paths, task names a reproducibility
│   ├── providers/                   # Ollama/embedding provider hranice
│   ├── datasets/                    # Loading, príprava a splitovanie datasetov
│   ├── finetuning/                  # LoRA/QLoRA pipeline a training engine
│   ├── ingestion/                   # Leakage-safe corpus a chunking pipeline
│   ├── vectorstore/                 # Izolovaná Chroma persistence vrstva
│   ├── retrieval/                   # Retrieval, Single RAG, MultiRAG a RRF
│   ├── approaches/                  # Direct/RAG/MultiRAG prompt stratégie
│   ├── inference/                   # Prompting, generation a structured output
│   ├── evaluation/                  # Testing/refactoring metriky a reporting
│   ├── experiments/                 # Resumable smoke experiment orchestration
│   ├── benchmarks/                  # TestBench, SWE-Refactor a smoke kontrakty
│   ├── models/                      # Zdieľané HF model/tokenizer/adapter loading
│   ├── cli/                         # Manuálne RAG CLI
│   ├── env/                         # Runtime readiness CLI
│   └── ui/                          # Gradio prezentačná a debug vrstva
│
├── scripts/                         # Tenké spustiteľné workflow vstupy
│   ├── datasets/                    # Príprava a audit datasetov
│   ├── finetuning/                  # Training, readiness a masking kontroly
│   ├── retrieval/                   # Index building a runtime kontroly
│   ├── inference/                   # Samostatné generation utility
│   ├── evaluation/                  # Metrics, reports a evaluation runs
│   └── experiments/                 # Benchmark a experiment orchestration
│
├── tests/                           # Automatické unit a integration testy
│   ├── datasets/                    # Dataset, split a smoke invariants
│   ├── finetuning/                  # Model/training config kontrakty
│   ├── retrieval/                   # Embedding, Chroma, RAG a WSL runtime
│   ├── inference/                   # Generation a shared runner
│   ├── evaluation/                  # Evaluation metriky
│   ├── experiments/                 # Benchmark orchestration
│   └── ui/                          # UI service a mapping
│
├── data/                            # Lokálne dáta a verziované smoke fixtures
│   ├── raw/                         # Zdrojové datasety (veľké sú ignorované)
│   ├── processed/                   # Reprodukovateľné odvodené splity
│   ├── chroma/                      # Lokálna ChromaDB persistence
│   └── smoke/                       # handcrafted_smoke_v1, nikdy sa neindexuje
│
├── artifacts/                       # Generované a handoff artefakty
│   ├── finetuning/                  # Adaptéry, checksumy a checkpoint metadata
│   ├── retrieval/                   # Index artefakty a index reporty
│   └── experiments/                 # Ignorované runs, audity, agregácie a reporty
│
├── docs/                            # Technická a metodologická dokumentácia
│   ├── architecture/                # Systémová a repository mapa
│   ├── datasets/                    # Dataset kontrakty
│   ├── finetuning/                  # Dizajn a runbooky tréningu
│   ├── retrieval/                   # RAG a embedding dokumentácia
│   ├── evaluation/                  # Evaluation runbooky
│   ├── experiments/                 # Experiment design a benchmark runbooky
│   ├── thesis/                      # Reprodukovateľný akademický handoff
│   └── ui/                          # UI dokumentácia
│
├── README.md                        # High-level vstup do projektu
├── devinfo.md                       # Technický handoff a záväzné pravidlá
└── pyproject.toml                   # Python package a dependencies
```

Detailné vlastníctvo balíkov a Mermaid diagram sú v
[Project map](docs/architecture/project_map.md).

### Main project areas

#### `datasets/`

Pripravuje, načítava a bezpečne splituje dáta pre training, retrieval aj
benchmark evaluation. Datasetové roly a manifesty bránia indexovaniu testovacích
alebo smoke prípadov.

#### `finetuning/`

Aktívna LoRA/QLoRA výskumná vetva: training datasety, prompt masking, model
setup, checkpoint/resume a adapter handoff. Nie je náhradou za retrieval.

#### `retrieval/`

Aktívna vetva nad Ollama `bge-m3`, ChromaDB, Single RAG, MultiRAG a Reciprocal
Rank Fusion. `ingestion/` izoluje bezpečnú stavbu korpusu a `vectorstore/`
izoluje persistence kontrakt.

#### `inference/`

Spoločná runtime vrstva pre canonical prompting, Direct/RAG/MultiRAG execution,
Ollama generation, structured output a auditovateľné experiment records.

#### `evaluation/`

Deterministická evaluácia testing a refactoring výstupov, prediction IO,
executable kontroly, metriky, agregácie a reporty.

#### `experiments/`

Vyberá dataset, model, approach a evaluation protocol. Orchestration skladá
existujúce inference/retrieval/evaluation komponenty a neimplementuje ich znova.

#### `ui/`

Tenká Gradio prezentačná a debug vrstva nad spoločnými službami; nemá vlastný
retrieval ani modelový pipeline.

Fine-tuning, Direct LLM, RAG, MultiRAG a Evaluation sú samostatné aktívne
výskumné vetvy diplomovej práce, nie legacy alternatívy.

## Datasets and Benchmarks

| Dataset | Rola |
|---|---|
| Methods2Test | testing dáta pre tréning, retrieval a kontrolované splity |
| SWE-Refactor | refactoring benchmark a projektové prípady |
| TestBench | executable testing benchmark |
| `handcrafted_smoke_v1` | malý deterministický smoke/regression dataset pre validáciu pipeline |

`handcrafted_smoke_v1` má presne **24 prípadov**: 12 testing a 12 refactoring.
Nie je indexovaný ani použitý na training; slúži iba na smoke, regresnú a
pipeline validáciu.

## Experiment Flow

```text
Dataset / Benchmark
        │
        ▼
┌─────────────────────────────┐
│          Approach           │
│   Direct / RAG / MultiRAG   │
└──────────────┬──────────────┘
               │
               ▼
        Shared Inference
               │
               ▼
          Evaluation
               │
               ▼
       Metrics + Reports

Training Dataset
        │
        ▼
   Fine-tuning
        │
        ▼
  Adapter / Model
        │
        ▼
    Evaluation
```

## Current Baseline

| Komponent | Baseline |
|---|---|
| Runtime | WSL/Linux |
| Generation | Ollama + `qwen2.5-coder:7b` |
| Embeddings | Ollama + `bge-m3` (1024 dimensions) |
| Vector store | lokálna ChromaDB |
| Single RAG | `mixed` |
| MultiRAG | `testing_db` + `refactoring_db` |
| Fusion | Reciprocal Rank Fusion (`k=60`) |
| Top-k | 5 |
| Baseline fingerprint | `74cc0a39be0c4d7f193fc749d8a40d448e4c364bef0b2c9eca19190c8db79e8f` |

Windows je iba hostiteľský OS. Windows Ollama ani výsledky z iného runtime sa
nemajú miešať s finálnymi experimentmi. Immutable kontrakt, digesty, prompt
hashe a corpus identity sú v `docs/experiments/baseline_v1.md`.

## Project Status

| Area | Status |
|---|---|
| Dataset preparation | Ready |
| Fine-tuning pipeline | Implemented |
| Retrieval / Chroma | Implemented |
| Single RAG | Implemented |
| MultiRAG | Implemented |
| Handcrafted smoke dataset | Ready |
| Prompt fairness | Implemented; audit PASS |
| `SmokeExperimentRunner` | Implemented |
| Six-run mini pilot | Completed; 6/6 latest runs successful |
| `baseline_v1` freeze | Complete; preflight and fingerprint enforcement active |
| Full benchmark evaluation | Pending |
| Ontology / GraphRAG | Future |

Canonical smoke orchestration:

```bash
python -m llm_ontology.experiments.smoke \
  --config configs/experiments/baseline_v1.yaml \
  --dry-run
```

Runner podporuje filtre `--task`, `--difficulty`, `--mode` a `--case`, bezpečné
resume, `--retry-failed` a explicitný `--force`. Default matrix obsahuje 24
smoke prípadov × 3 režimy = 72 plánovaných behov; plný matrix zatiaľ nebol
spustený.

## Next Steps

1. Manuálne skontrolovať frozen config a šesť-runový pilot/retrieval trace.
2. Až po schválení spustiť celý 72-run `baseline_v1` smoke matrix.
3. Pokračovať plnou TestBench/SWE-Refactor evaluáciou pod tým istým freeze
   kontraktom.
4. Každú zmenu promptu/modelu/retrievalu zaviesť ako `baseline_v2`.
5. Ontology/GraphRAG zaradiť až ako samostatnú budúcu experimentálnu vetvu.

## Quick start

V čistom WSL clone:

```bash
python3.11 -m venv .venv_wsl
source .venv_wsl/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,rag,ui]"

ollama pull bge-m3
ollama pull qwen2.5-coder:7b
ollama serve
```

V ďalšom termináli:

```bash
source .venv_wsl/bin/activate
python -m llm_ontology.env check
python -m llm_ontology.ui
```

UI je predvolene dostupné na `http://127.0.0.1:7860`. Konfigurácia je v
`configs/ui/local.yaml`.

## Architecture

```text
dataset manifests -> leakage audit -> pair-aware ingestion -> Ollama bge-m3
      -> Chroma collections -> retrieval/RRF -> shared prompt builder
      -> Ollama qwen2.5-coder:7b -> structured output -> evaluation record
```

`src/llm_ontology/` obsahuje zdieľanú implementáciu; `scripts/` sú tenké CLI
vstupy. Direct, RAG a MultiRAG používajú spoločný `RagExperimentRunner`, prompt
builder, generation provider a experiment log. UI iba volá tieto služby a
vykresľuje ich auditovateľný trace.

## Data and indexes

Dataset manifesty v `configs/datasets/manifests/` rozlišujú benchmark a
retrieval rolu. Benchmark/test prípady sa nikdy neindexujú. Produkčný builder
najprv vykoná identity a fingerprint audit a až potom vytvorí Chroma kolekcie:

```bash
python scripts/retrieval/build_production_indexes.py
```

Aktuálny lokálny baseline má `mixed=5739`, `testing_db=3978` a
`refactoring_db=1761` dokumentov. Literatúra zatiaľ nie je súčasťou baseline.
Chroma dáta v `data/chroma/`, spracované datasety, modely a generované výsledky
sú zámerne mimo Git histórie; reprodukovateľnosť zabezpečujú configy, dataset
manifesty, checksumy a malé textové reporty.

## CLI examples

```bash
python -m llm_ontology.cli.rag \
  --config configs/retrieval/ollama_bge_m3.yaml \
  query --collection mixed \
  --query "Generate JUnit tests for integer division"

python -m llm_ontology.cli.rag \
  --config configs/retrieval/ollama_bge_m3.yaml \
  query --mode multi_collection_rag \
  --collections tests refactor \
  --query "Refactor this Java method"
```

## Documentation

- [Developer/agent context](devinfo.md)
- [Project map](docs/architecture/project_map.md)
- [Architecture](docs/architecture/system_architecture.md)
- [RAG and MultiRAG baseline](docs/retrieval/rag_phase2.md)
- [Ollama embeddings](docs/retrieval/ollama_embeddings.md)
- [UI](docs/ui/overview.md)
- [Experiment design](docs/experiments/design.md)
- [Frozen baseline_v1 contract](docs/experiments/baseline_v1.md)
- [Handcrafted smoke dataset](docs/datasets/handcrafted_smoke.md)
- [Legacy cleanup report](docs/architecture/legacy_cleanup_report.md)
- [Commit and artifact policy](docs/architecture/git_commit_policy.md)

Fine-tuning, retrieval, inference, evaluation, benchmark execution a UI sú
samostatné aktívne výskumné oblasti. Konkrétny baseline používa iba ich
explicitne nakonfigurovanú kombináciu.

## Testing

```bash
ruff check .
python -m compileall src
pytest
git diff --check
```

Testy používajú mock providerov a dočasné indexy; nevytvárajú ani nemenia
produkčné Chroma kolekcie. Ďalší metodický krok je manuálna kontrola mini pilotu,
schválenie 72-run smoke matrixu a až potom batch evaluácia nad oboma benchmarkmi.
