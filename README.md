# LLM Ontology Experiment

Experimentálny repozitár pre porovnanie lokálnych jazykových modelov pri dvoch
úlohách softvérového inžinierstva nad Java kódom:

- generovanie JUnit testov,
- refaktoring zdrojového kódu.

Hlavný model je **Qwen2.5-Coder-7B-Instruct**. Projekt obsahuje dátovú pipeline,
LoRA/QLoRA fine-tuning, direct inferenciu, proxy metriky a benchmark adaptéry.
RAG má implementovaný kontrolovaný baseline; finálny literárny korpus a ostré
experimenty zostávajú vypnuté do schválenia dataset manifestov.

## Aktuálny stav

Presné runtime verzie a group-safe split pravidlá sú v
[environment a split locku](docs/experiment_environment_and_splits.md).

Aktualizované: **2026-07-19**

| Oblasť | Stav | Poznámka |
|---|---|---|
| Dataset pipeline | hotová | Methods2Test, MaRV, ML4Refactoring a finálne mixy |
| Fine-tuning | hotový | LoRA/QLoRA, masking, resume a readiness kontroly |
| Direct inference | hotová | Hugging Face a Ollama backend |
| TestBench adaptér | hotový | 108 prípadov; source/simple/full prompt varianty |
| TestBench Maven evaluator | hotový | bezpečný dry-run, compile/test a obnova súborov |
| SWE-Refactor adaptér | hotový | 1 099 pure-refactoring prípadov s referenciami |
| RAG fáza 1 | hotová | ChromaDB, oddelené kolekcie, ingestovanie, filtre, trace a mock providery |
| RAG fázy 2–3 | implementované | manifesty, Java/PDF parsing, Jina kandidát, lifecycle, Ollama a kontrolovaný runner |
| MultiRAG a ontology RAG | plán | routing, fusion, ontológia a reranking patria do ďalších fáz |
| JaCoCo/PIT v novom evaluatore | plán | potrebné pre plnú reprodukciu TestBench metrík |

## Rýchla Python kontrola

```bash
python -m pip install -e ".[dev,rag]"
python -m compileall -q src scripts tests
python -m pytest -q
python scripts/benchmarks/inspect_benchmarks.py
```

Očakávaný inventár je 108 TestBench a 1 099 SWE-Refactor prípadov.

## Štruktúra

```text
benchmarks/                 vendored TestBench a SWE-Refactor dáta/projekty
configs/
├── benchmarks/             benchmark a reproducibility nastavenia
├── experiments/            direct a vypnuté RAG/multi-RAG templates
├── models/                 Windows, WSL a Ollama modely
├── finetuning/             LoRA/QLoRA tréning
└── evaluation/             modely a datasety pre evaluáciu

src/llm_ontology/
├── data/                   dataset pipeline
├── benchmarks/             adaptéry, readiness a bezpečný evaluator
├── models/                 model/tokenizer/LoRA loading
├── training/               fine-tuning engine
├── inference/              modelové backendy a prompting
├── approaches/             generation approach kontrakty
├── retrieval/              retrieval pipeline, token budget a trace
└── evaluation/             metriky a reportovanie
```

Detailné hranice sú v [architektúre](docs/architecture.md).

## RAG fáza 1

RAG je vložený do existujúcej architektúry: datasety naďalej vlastní `data/`,
`ingestion/` ich pripravuje pre `vectorstore/`, `retrieval/` vracia auditovateľný
trace, `approaches/` skladá bezpečný prompt a `inference/` volá zameniteľný LLM
provider. Direct inference, fine-tuning a existujúca evaluácia zostali nezmenené.

Aktuálne fungujú režimy `no_rag`, `single_collection_rag` a `metadata_rag`.
Predvolená politika povoľuje iba `train` split a rovnaké dáta sa neduplikujú
vďaka SHA-256 hashu normalizovaného obsahu.

Rýchly lokálny príklad:

```powershell
python -m llm_ontology.cli.rag --config configs/retrieval/base.yaml index `
  --loader dataset `
  --input data/samples/testing_methods2test_sample.json `
  --dataset methods2test-sample-v1 `
  --collection test_examples `
  --split train

python -m llm_ontology.cli.rag --config configs/retrieval/base.yaml query `
  --collection test_examples `
  --query "Generate a JUnit test for a Java utility method"
```

Predvolený deterministický embedding provider je iba testovací mock, nie model
pre výsledky diplomovej práce. Kompletný popis, bezpečnostné pravidlá a známe
obmedzenia sú v [RAG fáze 1](docs/rag_phase1.md) a v
[kontrolovanom baseline fáz 2–3](docs/rag_phase2.md).

## TestBench: čistý LLM baseline

Pôvodný upstream `execute_test.py` nepoužívame. Obsahuje hardcoded Linux cesty,
chybný import, nedokončený prompt a rizikové prepisovanie testov. Náš evaluator
odvodzuje všetky cesty z `--benchmark-root`, kontroluje, že zostávajú v
benchmarku, a v `finally` obnovuje pôvodný súbor.

### Požadované prostredie

- Maven na `PATH`,
- JDK 8 v `TESTBENCH_JAVA8_HOME`,
- JDK 17 v `TESTBENCH_JAVA17_HOME`,
- spustený Ollama a model `qwen2.5-coder:7b`,
- sieť pri prvom Maven behu na stiahnutie dependencies,
- odporúčané aspoň 15 GiB voľného miesta.

Readiness kontrola:

```powershell
python scripts/benchmarks/check_readiness.py --backend ollama --model-name qwen2.5-coder:7b
```

Canary generation:

```powershell
python scripts/benchmarks/run_benchmark.py `
  --benchmark testbench `
  --context-level source `
  --backend ollama `
  --model-name qwen2.5-coder:7b `
  --temperature 0 `
  --seed 42 `
  --limit 1 `
  --output evaluation/predictions/testbench_direct_canary.jsonl
```

Evaluation dry-run:

```powershell
python scripts/benchmarks/evaluate_testbench.py `
  --predictions evaluation/predictions/testbench_direct_canary.jsonl `
  --dry-run `
  --output evaluation/metrics/testbench_direct_canary_plan.jsonl
```

Reálny Maven canary:

```powershell
python scripts/benchmarks/evaluate_testbench.py `
  --predictions evaluation/predictions/testbench_direct_canary.jsonl `
  --repair-package `
  --limit 1 `
  --timeout 600 `
  --output evaluation/metrics/testbench_direct_canary.jsonl
```

Kompletný postup vrátane full 108-case behu je v
[TestBench runbooku](docs/testbench_runbook.md).

## Benchmark protokol

TestBench prompt obsahuje target package, class, method a zvolený context level.
Model musí vrátiť jeden kompletný JUnit Jupiter source file. Každý generation
záznam uchováva model, backend, temperature, top-p, max tokens a seed.

Pre férové porovnanie treba zmraziť:

- model digest a sampling parametre,
- `source`, `simple` alebo `full` context variant,
- počet generácií na prípad,
- package repair policy,
- Maven timeout a flags,
- zoznam prípadov, ktorých projekt sa baseline nezostaví.

Aktuálny evaluator meria compile/test outcome. JaCoCo coverage a PIT mutation
score doplníme pred tvrdením, že reprodukujeme celý pôvodný TestBench protokol.

## Datasety

Normalizovaný JSONL záznam:

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "domain": "testing alebo refactoring",
  "source": "methods2test / ml4refactoring / marv"
}
```

| Dataset | Train | Val | Test |
|---|---:|---:|---:|
| testing | 4000 | 500 | 500 |
| refactoring_marv | 478 | 100 | 108 |
| refactoring_ml4ref | 4000 | 500 | 500 |
| refactoring | 4478 | 600 | 608 |
| combined | 8000 | 1000 | 1000 |

## Ďalší postup

1. nainštalovať a nakonfigurovať JDK 8, JDK 17, Maven a Ollama model,
2. prejsť 1-case Maven canary na každom z 9 projektov,
3. zmraziť direct baseline protokol,
4. doplniť JaCoCo/PIT,
5. vybrať a zmraziť reálny embedding model pre RAG experimenty,
6. implementovať Java-aware chunking, routing a MultiRAG fázu 2.
