# LLM Ontology Experiment

[![CI](https://github.com/patrik-on/llm-ontology-experiment/actions/workflows/ci.yml/badge.svg)](https://github.com/patrik-on/llm-ontology-experiment/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Diplomová práca: Qwen2.5-Coder-7B na dvoch Java úlohách, generovaní JUnit testov
(Methods2Test) a refactoringu (SWE-Refactor + MaRV + ML4Ref). Každá úloha porovnáva
osem ramien na tých istých 100 prípadoch, jeden pokus na bunku a bez opráv výstupu.

| Rameno | Čo dostane model |
|---|---|
| `qwen_base` | iba zadanie (Ollama) |
| `onto_project` | zadanie + blok projektovej ontológie z dodaného kódu |
| `skills` | zadanie + procesný návod `SKILL.md` |
| `skills_onto` | `skills` + blok ontológie |
| `rag_single` | zadanie + 3 príklady vyhľadané v Chroma indexe (bge-m3) |
| `ft_testing` / `ft_refactoring` | LoRA adaptér v3 (HF, NF4) |
| `ft_v3_onto` | adaptér v3 + blok ontológie |
| `ft_onto` | adaptér trénovaný s blokom ontológie + blok |

## Výsledky

Úspešné prípady zo 100 (testing: class pass, refactoring: structural success):

| Rameno | Testing | Refactoring |
|---|---|---|
| qwen_base | 22 | 60 |
| onto_project | 22 | 55 |
| skills | 21 | 49 |
| skills_onto | 23 | 54 |
| rag_single | 14 | 37 |
| ft_testing / ft_refactoring | 53 | 68 |
| ft_v3_onto | 48 | 67 |
| ft_onto | 51 | 67 |

Žiadny z piatich primárnych párov nie je významný (Holm p = 1,0 v oboch úlohách).
FT ramená bežia na inom backende (HF NF4) než ostatné (Ollama Q4), preto je ich
porovnanie so základom iba opisné. Podrobnosti:

- [Testing report](docs/results/testing_summary.md) (`testing-matrix-20261122-rag2`)
- [Refactoring report](docs/results/refactoring_summary.md) (`refactoring-matrix-20261121`)
- [Hĺbková analýza](docs/results/deep_analysis.md), [príklady](docs/results/deep_analysis_examples.md),
  [čísla v JSON](docs/results/deep_analysis.json)

## Replikácia

Dá sa ísť troma úrovňami. Každá ďalšia potrebuje viac dát, času a GPU.

| Úroveň | Čo overí | Potrebuje |
|---|---|---|
| A. Kód | testy, plány behov | iba Python |
| B. Reporty z existujúcich behov | všetky čísla v `docs/results/` | run adresáre (odovzdávajú sa zvlášť) |
| C. Celý experiment | dáta → index → tréning → oba evaly | GPU so 16 GB VRAM, ~120 GB disku, datasety, asi 2 dni výpočtu |

### Prostredie, na ktorom experiment bežal

| Časť | Verzia |
|---|---|
| OS | Windows + WSL2 Ubuntu 24.04.3 LTS |
| GPU | NVIDIA GeForce RTX 3080 Laptop, 16 GB VRAM, driver 596.36 |
| Python | 3.13.11; torch 2.15.0+cu132, transformers 4.57.6, peft 0.21.3, bitsandbytes 0.50.2, accelerate 1.16.0, datasets 5.0.1, chromadb 1.5.9, rdflib 7.6.0, scipy 1.18.1 |
| Ollama | 0.15.2; `qwen2.5-coder:7b` Q4_K_M, digest `dae161e27b0e…4364`; `bge-m3` F16, digest `7907646426…6bab` |
| HF model | Qwen2.5-Coder-7B-Instruct (15 GB), tréning a FT ramená v NF4 |
| Java | Temurin 11.0.33 (testing), OpenJDK 17.0.21 (RefactoringMiner, Maven 3.9.16), Temurin 8u512 (SWE buildy) |
| Disk | ML4Ref 77 GB, Methods2Test 1,2 GB, Chroma index 330 MB, SWE git mirrory 0,5 GB, model 15 GB + 5,8 GB Ollama |

Čas na tomto stroji: tréning štyroch adaptérov spolu ≈ 28 h (testing ≈ 4 h každý,
refactoring 8,5 až 11,7 h), testing eval ≈ 3 h, refactoring eval ≈ 14 h.
Celé digesty Ollama modelov sú v `ollama_identity.json` každého behu. Presný commit
Methods2Test a revízia HF modelu zaznamenané nie sú; behy namiesto toho pinujú hashe
použitých súborov (`freeze.json`, `hf_identity/`).

Všetky príkazy sa spúšťajú vo WSL z koreňa repozitára. Repozitár môže byť na
`/mnt/c`, ale checkpointy, behy a Java buildy patria na natívny WSL disk
(`~/experiments`, `~/benchmark-work`), inak ich spomaľuje OneDrive a NTFS.

### A. Kód (bez GPU a dát)

```bash
python -m venv .venv_wsl && source .venv_wsl/bin/activate
pip install -e ".[dev,rag,ontology]"
python -m pytest -q -rs
ruff check src scripts tests
python scripts/benchmarks/run_testing_matrix.py --run-id testing-plan --dry-run
python scripts/benchmarks/run_refactoring_matrix.py --run-id refactoring-plan --dry-run
```

Testy `local_data` a `rag` sa bez lokálnych dát alebo `chromadb` preskočia s dôvodom.
`--dry-run` nič nezapisuje a nevolá model.

### B. Reporty a analýza z existujúcich behov

Skopíruj odovzdané run adresáre do `artifacts/evaluation/runs/`
(`testing-matrix-20261121`, `testing-matrix-20261122-rag2`, `refactoring-matrix-20261121`).

**Analýza** číta iba uložené výsledky a beží na aktuálnom main:

```bash
pip install -e ".[analysis]"
python scripts/analysis/deep_analysis.py     # zapíše artifacts/analysis/deep-20261122/
```

**Prepočet reportu** (`--report-only`) najprv overí `freeze.json`: hashe vstupov,
modelov, indexu, Javy aj zdrojového kódu, s ktorým beh bežal. Preto prejde iba na
commite daného behu, na neskoršom kóde skončí chybou `Frozen dependency changed`.

| Beh | Commit | Čo obsahuje |
|---|---|---|
| `testing-matrix-20261121` | `2c3a35d` | testing, 7 ramien + 3 bunky `rag_single` |
| `testing-matrix-20261122-rag2` | `4542d53` | finálny testing, všetkých 8 ramien |
| `refactoring-matrix-20261121` | `2c3a35d` | finálny refactoring |

```bash
git checkout --detach 4542d53          # v hlavnom checkoute, nie vo worktree
python scripts/benchmarks/run_testing_matrix.py --run-id testing-matrix-20261122-rag2 --report-only
git checkout --detach 2c3a35d
python scripts/benchmarks/run_refactoring_matrix.py --run-id refactoring-matrix-20261121 --report-only
git checkout main
```

Na týchto commitoch report bajtovo zopakuje uložené `reports/summary.md` aj
`reports/aggregate.json` (overené 2026-11-22). `freeze.json` pinuje súbory
absolútnymi cestami, takže kontrola prejde iba pri rovnakom umiestnení repozitára,
dát a modelov ako na pôvodnom stroji. Na inom stroji sa dá použiť analýza vyššie
a kód behu je uložený aj v jeho `source_snapshot/`.

Report prepíše `reports/` v run adresári. Ak ich chceš zachovať, spusti ho na kópii.
`testing-matrix-20261122-rag2` je pokračovanie `testing-matrix-20261121`, ktoré
dokončilo zastavené rameno `rag_single` na tých istých prípadoch (`continuation.json`).

### C. Celý experiment

**1. Inštalácia a cesty**

```bash
pip install -e ".[dev,rag,ontology,training,analysis]"
# premenné z .env.example exportuj v ~/.bashrc (projekt ich sám nenačíta)
python -m llm_ontology.env check
```

Konfigurácie nemajú absolútne cesty. Používajú `${LLM_ONTOLOGY_WORK_ROOT}`
(JDK, jary, git mirrory, buildy), `${LLM_ONTOLOGY_MODELS_ROOT}` (HF modely) a
`${LLM_ONTOLOGY_DATASETS_ROOT}` (veľké surové datasety), pozri [.env.example](.env.example).

**2. Modely**

```bash
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct \
  --local-dir "$LLM_ONTOLOGY_MODELS_ROOT/huggingface/Qwen2.5-Coder-7B-Instruct"
ollama pull qwen2.5-coder:7b
ollama pull bge-m3
```

Freeze overuje digest Ollama modelu. Iný digest znamená iný experiment a nový run ID.

**3. Java nástroje** (do `$LLM_ONTOLOGY_WORK_ROOT`)

- `deps/jdk-11.0.33+10` (Temurin 11, testing harness) a `deps/refactoring-jdk8` (Temurin 8, SWE buildy).
- Systémový JDK 17 a Maven 3.9 na spustenie RefactoringMinera a SWE buildov (bežia offline, `mvn -o`).
- `downloads/`: `junit-platform-console-standalone-1.11.4.jar`, `assertj-core-3.27.3.jar`,
  `hamcrest-2.2.jar`; JaCoCo 0.8.13 agent a CLI podľa [jacoco_v1.json](configs/evaluation/jacoco_v1.json).
- RefactoringMiner 3.0.10: `cd tools/refactoring-miner && mvn -q package`.

**4. Datasety**

| Dataset | Zdroj | Kam |
|---|---|---|
| Methods2Test | <https://github.com/microsoft/methods2test> (MIT; `corpus/json`, `dataset/train.tar.bz2`, `dataset/eval.tar.bz2`) | `data/raw/methods2test/` |
| MaRV | <https://zenodo.org/records/14450098> | `data/raw/marv/dataset/MaRV.json` |
| ML4Refactoring | <https://zenodo.org/records/3547639> (`all.zip`) | `$LLM_ONTOLOGY_DATASETS_ROOT/ml4refactoring/all/dataset` |
| SWE-Refactor | <https://zenodo.org/records/17196850> (DOI 10.5281/zenodo.17196850) | `benchmarks/swe-refactor/SWE-Refactor/` |

Postup a hashe SWE-Refactor sú v [zázname o stiahnutí](docs/datasets/swe_refactor_zenodo_acquisition_2026-11-12.md).

**5. Spracované dáta v1** (zdroj RAG korpusu, kontrola úniku a výberu kohorty)

```bash
python scripts/datasets/prepare_methods2test.py
python scripts/datasets/prepare_ml4refactoring.py
python scripts/datasets/prepare_marv.py
python scripts/datasets/prepare_final_datasets.py
```

**6. RAG index** (iba embeddingy bge-m3, žiadne generovanie)

```bash
python scripts/retrieval/build_production_indexes.py --config configs/retrieval/ollama_bge_m3_v3.yaml
```

Opis vyhľadávania: [rag_v3.md](docs/retrieval/rag_v3.md).

**7. Tréningové dáta v3 a štyri adaptéry**

```bash
python scripts/datasets/prepare_v3_eval_aligned.py testing
python scripts/datasets/prepare_v3_eval_aligned.py refactoring
for c in b2_testing b2_refactoring b2_testing_onto b2_refactoring_onto; do
  python scripts/finetuning/check_finetuning_ready.py --config configs/finetuning/training_${c}_wsl.yaml
  python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_${c}_wsl.yaml
done
```

Builder vyrobí `data/processed/v3/` a `data/processed/v3_onto/` so spoločným manifestom.
Adaptéry sa uložia do `~/experiments/llm-ontology-v3/<názov>/checkpoints/final_adapter`.
Podrobnosti, prerušenie a pokračovanie: [v3_runbook.md](docs/finetuning/v3_runbook.md).

**8. Refactoring kohorta**

Vydaná kohorta 100 úloh je v repe
([manifest](data/validation/refactoring_mixed_v1/manifest.json)). Na novom stroji ju
znova over a vydaj (sťahuje súbory, buildí SWE projekty, žiadne volania modelu):

```bash
python scripts/benchmarks/run_refactoring_matrix.py --run-id <nové-id-poolu> --prepare-pool
python scripts/ontology/check_cohort.py      # kontrola blokov ontológie pre celú kohortu
```

**9. Evaly** (každý beh potrebuje nový run ID)

```bash
# skúška s 1 prípadom (8 volaní)
python scripts/benchmarks/run_testing_matrix.py --run-id testing-smoke --cases 1
# plný beh: 100 × 8
python scripts/benchmarks/run_testing_matrix.py --run-id testing-<dátum>
python scripts/benchmarks/run_refactoring_matrix.py --run-id refactoring-<dátum> --cases all
```

Runner nič neinštaluje ani netrénuje. Pred generovaním zmrazí všetky prompty a
identity. Prerušená zaplatená bunka sa nikdy neopakuje. Ak rameno zastaví chyba
pred volaním modelu, dá sa dokončiť na tých istých prípadoch:
`--run-id <nové-id> --continue-from <zdrojové-id> --arm <arm>`
([postup](docs/evaluation/testing_matrix_v1.md)).

**10. Analýza**

```bash
python scripts/analysis/deep_analysis.py \
  --testing-run artifacts/evaluation/runs/<testing-id> \
  --refactoring-run artifacts/evaluation/runs/<refactoring-id> \
  --out artifacts/analysis/<názov>
```

Úvodné zhrnutie v `results.md` sa berie zo súboru `--summary` (pre tento beh
`scripts/analysis/deep_analysis_summary_20261122.md`); ostatné čísla počíta skript.

## Pravidlá experimentu

- Zmrazený beh, bajty promptu a `configs/skills/*/SKILL.md` sa nemenia. Zmena experimentu = nový run ID.
- Jeden pokus na bunku, žiadne opravy ani opakovania; chyby ostávajú v menovateli.
- Primárne páry a Holmova korekcia sú vopred dané v JSON konfigurácii matíc.
- Ontológia vzniká iba z kódu dodaného modelu, gold odpoveď do nej nesmie preniknúť.

## Mapa repozitára

| Kde | Čo |
|---|---|
| `scripts/benchmarks/` | jediné dva eval runnery |
| `src/llm_ontology/benchmarks/` | orchestrácia matíc, hodnotenie, štatistika |
| `src/llm_ontology/ontology/` | blok projektovej ontológie (RDF z dodaného kódu) |
| `src/llm_ontology/inference/prompting/` | prompt profily |
| `scripts/datasets/`, `scripts/finetuning/`, `scripts/retrieval/` | dáta, tréning, index |
| `scripts/analysis/` | hĺbková analýza výsledkov |
| `configs/` | modely, matice, retrieval, tréning, pinnuté `SKILL.md` |
| `docs/` | [index dokumentácie](docs/README.md): eval, výsledky, tréning, retrieval; datované záznamy v `docs/archive/` |
| `thesis_materials/` | podklady na písanie práce |

Pre agentov a nástroje je aktuálny zoznam aktívnych verzií v [AGENTS.md](AGENTS.md).

## Citácia a licencia

Kód je pod licenciou [MIT](LICENSE). Ak ho použiješ, cituj ho podľa [CITATION.cff](CITATION.cff)
(GitHub ponúka tlačidlo „Cite this repository“). Datasety majú vlastné licencie:
Methods2Test (MIT), SWE-Refactor (CC-BY-4.0) a MaRV a ML4Refactoring podľa ich záznamov na Zenodo.
