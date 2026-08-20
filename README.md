# LLM Ontology Experiment

Experimentálny repozitár porovnáva lokálne jazykové modely pri dvoch úlohách
nad Java kódom: generovanie JUnit testov a refaktoring. Aktuálny baseline
porovnáva tri režimy pri rovnakom modeli, prompt contracte a evaluácii:

- **Direct LLM** (`no_rag`) bez retrievalu,
- **RAG** (`single_collection_rag`) nad kolekciou `mixed`,
- **MultiRAG** (`multi_collection_rag`) nad oddelenými kolekciami s RRF.

Ontológia, GraphRAG, router, reranker a literárna kolekcia nie sú súčasťou
aktuálneho baseline.

## Project Structure

Projekt je rozdelený podľa samostatných výskumných oblastí diplomovej práce:

| Oblasť | Účel | Hlavné umiestnenie |
|---|---|---|
| Datasets | príprava Methods2Test, ML4Refactoring/MaRV, TestBench, SWE-Refactor a handcrafted smoke dát | `src/llm_ontology/datasets/`, `data/`, `configs/datasets/` |
| Fine-tuning | aktívny LoRA/QLoRA tréning, readiness, adaptéry a training configy | `src/llm_ontology/finetuning/`, `scripts/finetuning/`, `configs/finetuning/` |
| Retrieval | ingestion, leakage ochrana, embeddings, Chroma, RAG, MultiRAG a RRF | `src/llm_ontology/ingestion/`, `src/llm_ontology/vectorstore/`, `src/llm_ontology/retrieval/`, `scripts/retrieval/` |
| Inference | spoločné promptovanie, model execution, structured output a Direct/RAG/MultiRAG runner | `src/llm_ontology/inference/`, `src/llm_ontology/approaches/` |
| Evaluation | testing/refactoring metriky, executable checks, prediction IO a reporty | `src/llm_ontology/evaluation/`, `scripts/evaluation/` |
| Experiments | výber prípadov, modelov a režimov; benchmark orchestration a porovnanie | `configs/experiments/`, `scripts/experiments/` |
| UI | tenká Gradio prezentačná a debug vrstva nad spoločnými službami | `src/llm_ontology/ui/`, `configs/ui/` |

Podrobná mapa, vlastníctvo balíkov a diagram sú v
[Project map](docs/architecture/project_map.md).

## Runtime

Finálne experimenty bežia výhradne v jednom WSL/Linux prostredí:

| Komponent | Baseline |
|---|---|
| Generation | Ollama `qwen2.5-coder:7b` |
| Embeddings | Ollama `bge-m3`, 1024 rozmerov |
| Vector store | lokálna ChromaDB |
| MultiRAG fusion | RRF, `k=60` |
| UI | Gradio |
| Python | 3.11+ |

Windows je iba hostiteľský OS. Windows Ollama ani výsledky z iného runtime sa
nemajú miešať s finálnymi experimentmi.

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
- [Handcrafted smoke dataset](docs/datasets/handcrafted_smoke.md)
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
produkčné Chroma kolekcie. Ďalší metodický krok je zmrazenie baseline a následná
batch evaluácia Direct/RAG/MultiRAG nad oboma benchmarkmi.
