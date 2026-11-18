# LLM Ontology Experiment

Lokálne porovnanie piatich systémov pri dvoch Java úlohách:

- **Methods2Test:** generovanie JUnit testov pre extrahované metódy.
- **Refactoring:** spoločný SWE + MaRV + ML4Ref pool; SWE navyše overuje pôvodný projekt.

Obe matice porovnávajú **baseline, fine-tuned model, Single-RAG, MultiRAG a
baseline + existujúci skill**. Testing má default **100 prípadov** × 5 variantov (500 volaní); menší beh cez `--cases N`.
Refactoring má pripravených **100 úloh: 5 SWE + 35 MaRV + 60 ML4Ref**; podporuje
menší výber N aj všetkých 100, vždy bez opravných pokusov. MaRV/ML4Ref používajú
rozumný okolitý kontext a skórujú konkrétny zadaný refactoring; ďalšie zmeny sa
neskórujú. SWE má navyše pôvodné buildy/testy. Rozdiely HF/PEFT a Ollama
backendov sa zaznamenávajú; nejde o izolovanú abláciu FT adaptéra.

## Jediné dva eval runnery

Príkazy sa spúšťajú z koreňa repozitára vo WSL cez `.venv_wsl/bin/python`.

| Úloha | Runner | Protokol a postup |
|---|---|---|
| Testing | `scripts/benchmarks/run_testing_matrix.py` | [Methods2Test matica](docs/evaluation/testing_matrix_v1.md) |
| Refactoring | `scripts/benchmarks/run_refactoring_matrix.py` | [Zmiešaná refactoring matica](docs/evaluation/refactoring_matrix_v1.md) |

Bez modelových volaní a bez zápisov:

```bash
.venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py --run-id testing-plan --dry-run
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py --run-id refactoring-plan --dry-run
```

Príprava a zmrazenie vstupov bez generovania odpovedí:

```bash
.venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py --run-id NEW_TESTING_RUN --freeze-only
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py --run-id NEW_POOL_PREPARATION --prepare-pool
# Pool je už pripravený; nový beh môže použiť --cases N alebo --cases all --prepare-only.
```

Bez príznaku režimu runner spustí aj generovanie a hodnotenie. `--report-only`
načíta existujúci beh. Refactoring podporuje aj `--evaluate-only`.
Pred spustením treba lokálne modely/adaptéry, existujúci RAG index a Java nástroje;
matice netrénujú, neprebudovávajú index a neopravujú modelové odpovede.

## Výstupy

Jediný eval namespace je `artifacts/evaluation/runs/<run-id>/`.
Existujúce prípravné dôkazy zostali zachované:

- `testing-matrix-preparation-check-20261113`: jeden overený prípad, päť variantov.
- `mixed-context-pool-v4-20261113`: úplná QA 100 úloh.
- `refactoring-context-v4-ready-20261114`: pripravený výber všetkých 100 cez aktuálny runner.

Tieto prípravy majú **0 generovaní**. Príprava/hodnotiteľské QA nie sú skóre modelov.
Pool a jeho overenie sú opísané v [v4 prehľade](docs/evaluation/refactoring_context_v4_2026-11-13.md).
Súbory v `preparation`, `candidates`,
`preflight` a `reports` patria príslušnej matici; interné helpery nie sú ďalšie
spustiteľné eval protokoly. Staré piloty, samostatné full/smoke evaly, staré
konfigurácie, reporty a výstupy boli odstránené z aktívneho projektu.

## Zvyšok projektu

Tréning, surové/spracované datasety, modely/adaptéry, a RAG indexy
zostávajú oddelené od evaluácie. Datasetové audity a nástroje ako RefactoringMiner
či JaCoCo sú podklady/závislosti aktuálnych matíc, nie dodatočné eval runnery.

- [Mapa projektu](docs/architecture/project_map.md)
- [Tréning](docs/finetuning/v2_runbook.md)
- [Aktuálny retrieval](docs/retrieval/rag_v3.md)
- [Eval dokumentácia](docs/evaluation/README.md)
- [Podklady na písanie práce](thesis_materials/README.md) — metodické reporty,
  archivované handcrafted výsledky a dôkazy; nie ďalší aktívny eval runner.
- [Prečo sú aktuálne evaluácie takto navrhnuté](thesis_materials/reports/evaluation_design_2026-11-13.md)

## Inštalácia a lokálne cesty

```bash
python -m venv .venv_wsl && source .venv_wsl/bin/activate
pip install -r requirements.txt          # = pip install -e ".[dev,rag]"
pip install -e ".[training]"             # iba pre reálny fine-tuning
```

Konfigurácie neobsahujú absolútne cesty konkrétneho počítača. Používajú
premenné `${LLM_ONTOLOGY_WORK_ROOT}` (default `~/benchmark-work`: JDK, JUnit/JaCoCo
jary, git mirrory), `${LLM_ONTOLOGY_MODELS_ROOT}` (default `/mnt/c/models`) a
`${LLM_ONTOLOGY_DATASETS_ROOT}` (default `/mnt/c/datasets`). Na inom stroji ich
stačí exportovať, pozri [.env.example](.env.example).

Rameno `skills` používa pinnuté kópie `SKILL.md` v [configs/skills/](configs/skills/info.md)
(z `si-context-eval@57ce660`), takže susedný checkout už nie je potrebný.

## Kontroly implementácie

```bash
.venv_wsl/bin/python -m pytest -q -rs
.venv_wsl/bin/ruff check src scripts tests
```

Testy označené `local_data` potrebujú Gitom ignorované lokálne vstupy
(SWE-Refactor dataset a overlap audit v `artifacts/swe_overlap_audit_20261113/`),
testy `rag` potrebujú `chromadb`. Ak chýbajú, preskočia sa s dôvodom, takže čistý
klon a CI (`.github/workflows/ci.yml`) bežia zelene. Integračné kontroly
nevytvárajú experimentálne skóre modelov.
