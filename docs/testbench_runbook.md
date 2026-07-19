# TestBench direct-LLM runbook

Tento projekt nepoužíva pôvodný `benchmarks/TestBench-main/execute_test.py`.
Upstream skript má hardcoded Linux cesty, chybný import, shellové Maven príkazy
a môže prepísať existujúce testy. Náš tok používa read-only adaptér, spoločný
Ollama generator a bezpečný Maven evaluator.

## Čo meria aktuálna verzia

Aktuálne vieme pre každý zo 108 prípadov:

1. pripraviť jeden z troch prompt variantov (`source`, `simple`, `full`),
2. vygenerovať jeden kompletný JUnit Jupiter súbor,
3. bezpečne ho vložiť do správneho Maven modulu,
4. spustiť iba vygenerovanú testovaciu triedu,
5. zaznamenať `accepted`, `compile_error`, `test_error`, `maven_error` alebo
   `timeout`,
6. vždy obnoviť pôvodný súbor, ak nastala kolízia názvu.

JaCoCo line coverage a PIT mutation score zatiaľ nie sú súčasťou nového
evaluatora. Sú potrebné pre plnú reprodukciu všetkých TestBench metrík.

## Požiadavky

- Maven dostupný ako `mvn` na `PATH`.
- JDK 8 pre legacy projekty, nastavený v `TESTBENCH_JAVA8_HOME`.
- JDK 17 pre projekt `Java`, nastavený v `TESTBENCH_JAVA17_HOME`.
- Ollama na `http://localhost:11434`.
- Model `qwen2.5-coder:7b` stiahnutý v Ollama.
- Sieť pri prvom Maven behu, aby sa naplnila lokálna dependency cache.
- Aspoň 5 GiB voľného miesta; odporúčané je 15–20 GiB.

Legacy projekty deklarujú Java 6/7/8 source compatibility, kým projekt `Java`
vyžaduje Java 17. Preto jeden globálny JDK nie je spoľahlivý pre celý benchmark.

## 1. Nastavenie prostredia

PowerShell príklad:

```powershell
$env:TESTBENCH_JAVA8_HOME = "C:\Program Files\Eclipse Adoptium\jdk-8.0.x"
$env:TESTBENCH_JAVA17_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.x"
```

Overenie:

```powershell
python scripts/benchmarks/check_readiness.py `
  --backend ollama `
  --model-name qwen2.5-coder:7b
```

Príkaz skončí s exit code 1, pokiaľ chýba povinná časť prostredia.

## 2. Canary generovanie

Najprv jeden prípad s deterministickými parametrami:

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

## 3. Bezpečný evaluation dry-run

Dry-run validuje package, class name, Maven modul a cieľovú testovaciu cestu.
Nevytvorí Java súbor a nespustí Maven.

```powershell
python scripts/benchmarks/evaluate_testbench.py `
  --predictions evaluation/predictions/testbench_direct_canary.jsonl `
  --dry-run `
  --output evaluation/metrics/testbench_direct_canary_plan.jsonl
```

## 4. Canary Maven test

```powershell
python scripts/benchmarks/evaluate_testbench.py `
  --predictions evaluation/predictions/testbench_direct_canary.jsonl `
  --repair-package `
  --limit 1 `
  --timeout 600 `
  --output evaluation/metrics/testbench_direct_canary.jsonl
```

`--repair-package` iba doplní chýbajúci package declaration podľa benchmark
metadata. Túto voľbu treba zmraziť a používať rovnako pre všetky porovnávané
modely.

## 5. Celý direct baseline

Až keď canary kompiluje a Maven dependencies sú v cache:

```powershell
python scripts/benchmarks/run_benchmark.py `
  --benchmark testbench `
  --context-level source `
  --backend ollama `
  --model-name qwen2.5-coder:7b `
  --temperature 0 `
  --seed 42 `
  --limit 108 `
  --output evaluation/predictions/testbench_direct_source.jsonl

python scripts/benchmarks/evaluate_testbench.py `
  --predictions evaluation/predictions/testbench_direct_source.jsonl `
  --repair-package `
  --timeout 600 `
  --output evaluation/metrics/testbench_direct_source.jsonl
```

Pre prompt abláciu zopakuj generovanie s `--context-level simple` a `full`.
Model, seed, sampling parametre, počet generácií a repair policy musia zostať
rovnaké.

## Pred plným experimentom ešte zmraziť

- presný Ollama model digest, nie iba tag,
- `source`/`simple`/`full` experiment matrix,
- jednu alebo viac generácií na prípad,
- package repair policy,
- timeout a Maven flags,
- JaCoCo a PIT verzie, ak chceme plné TestBench metriky,
- postup pri projekte, ktorému zlyhá baseline build bez vygenerovaného testu.
