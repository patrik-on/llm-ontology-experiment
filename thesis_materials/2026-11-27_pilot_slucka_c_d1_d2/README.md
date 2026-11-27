# Pilot slučky C, D1, D2: stav k 27. 11. 2026

Runbook: [`docs/evaluation/repair_loop_v1.md`](../../docs/evaluation/repair_loop_v1.md).
Kód: `src/llm_ontology/repair/`, konfigurácia `configs/benchmarks/repair_loop_v1.json`,
báza D1 `configs/repair/rules_d1/`, testy `tests/repair/test_repair_loop.py`.

## Čo sa reálne spustilo

**Iba skúška mechanizmu s náhradným modelom.** Qwen, Java ani RefactoringMiner v tomto
prostredí nebežali, takže žiadne číslo nižšie nie je výsledok modelu.

| Čo | Výsledok |
|---|---|
| `pytest tests/repair` (náhradný model, skutočné fakty a SHACL) | 8 passed |
| celé `pytest -q` | 327 passed, 33 skipped (lokálne dáta, chromadb) |
| `run_repair_loop.py --mock` (3 ručne pripravené úlohy) | C 0/3, D1 0/3, D2 1/3 po 3 pokusoch, scenár je zostavený tak, aby to tak vyšlo |
| fakty a D1 na 10 skutočných vstupoch Parameterize Variable z kohorty | extrakcia prebehne na všetkých 10 |

Ručne pripravená skúška predvádza, čo zadanie žiada:

1. **Zamietnutie chybného návrhu** (úloha 1): pravidlo „nový parameter sa používa iba v logovaní“
   bez výnimky označí aj správny príklad, kde je cieľová metóda pomocná logovacia metóda.
   Zamietnuté s dôvodom `flags_correct_example`.
2. **Prijatie platnej úpravy** (úloha 2): to isté pravidlo ako spresnenie R2 s výnimkou
   `method_is_logging_helper`. Zachytí odložený chybný príklad, ktorý D1 nezachytí (R2 použitie
   nespáruje a vráti iba *nevieme posúdiť*), prepustí oba správne príklady a nespôsobí regresiu
   R2. Prijaté ako verzia v1. Úloha 2 sa sama opravuje ešte s v0.
3. **Použitie na ďalšej úlohe** (úloha 3, iná skupina): D2 v1 pridá hlásenie, ktoré D1 nemá.
   Obe opravné vetvy začínajú z tej istej prvej odpovede (report `loop_report.md` ich ukazuje
   vedľa seba).
4. Ďalej testy overujú, že sa D1 nezmení (hash), že po `freeze` sa D2 neposunie ani po
   opätovnom načítaní, že pri obnove sa volania ani zmena nezapočítajú dvakrát, že aktivácia
   čaká na úlohu z inej skupiny, že pri chýbajúcich príkladoch je výsledok `pending`, pri
   chýbajúcich faktoch `deferred`, a že návrh pri testovaní, ktorý iba zopakuje T3 (aj
   s výnimkou `assertThrows`), sa zamietne ako `duplicate_no_added_coverage`. Prompty nikdy
   neobsahujú overovacie príklady ani ich štítky.

## Ako je to postavené

- **Spoločný prvý pokus:** jedno generovanie na úlohu z promptu ramena `onto_project`
  (rovnaké zadanie aj blok faktov pre C, D1, D2), potom sa varianty rozvetvia.
- **Rozpočet:** najviac 3 pokusy vrátane spoločného a 1 rozbor po prvom opraviteľnom neúspechu.
  Diagnóza ide do opravy vo všetkých variantoch, D2 má navyše voliteľné pole `rule_proposal`.
- **Návrh pravidla:** model vyberá z uzavretého zoznamu šablón (`rules.TEMPLATES`), parametre,
  výnimku a hlásenie. SHACL vzniká deterministicky, voľný SHACL sa nespúšťa.
- **Overenie:** iba na príkladoch iných úloh (skupina = zadanie), autor ich nevidí.
- **Stav D2:** `rulebase_d2/ledger.jsonl` (append-only), verzie `vNNNN.json`, v0 = D1.

## Čo chýbalo a čo treba spustiť vo WSL

1. **Uložené výstupy.** Archív `refactoring-matrix-20261121.tar.zst` na Zenode existuje
   (5,4 MB), ale do tohto prostredia sa stiahnuť nedal. Preto zatiaľ nebežali kontrola verejného
   checkera na uložených výstupoch (L5, `--check-public-checker`) ani tvorba označených príkladov
   (`--build-pool`).
2. **Ručné štítky** pre asi 10 príkladov do `configs/repair/manual_labels_refactoring.json`.
3. **Pilot s Qwenom** na 10 úlohách Parameterize Variable.
4. **Testing** má zatiaľ iba skúšku mechanizmu (T3 na TTL príkladoch). Adaptér slučky pre
   testing (javac, JUnit, fakty z tiel testov) ešte nie je.

## Zistenia pri príprave

- **8 z 10 úloh Parameterize Variable mieri na metódu, ktorá vo vstupe neexistuje.** Požiadavka
  ML4Ref je opis udalosti RefactoringMinera, ktorá vzniká spolu s extrakciou metódy (napr.
  lokálna premenná `buffer` v `setProcessOutputStream` sa stane parametrom `line` novej metódy
  `stdout`). Pôvodné R2 predpokladalo, že ide o tú istú metódu. Fakty preto berú cieľovú metódu
  podľa mena z požiadavky a použitia párujú zo zdrojovej metódy.
- Prvý prípad kohorty (`ml4refactoring-004d47930c7d0adbff07a577`) je presne legitímna výnimka
  z pravidla o logovaní: nová metóda `stdout(line)` parameter iba loguje.
- Verejný checker porovnáva opis udalosti RefactoringMinera s textom požiadavky. Či dáva rovnaký
  verdikt ako `structural_success`, ukáže až L5 na uložených výstupoch.

## Odhad nákladov

Na 10 úloh: 10 spoločných generovaní a pre každý variant najviac 1 rozbor a 2 opravy, spolu
najviac 100 volaní. Pri predpoklade z návrhu C/D (~25 s na generovanie refaktoringu a ~8 s na
RefactoringMiner) je to do ~1 h. Report pilota (`--report-only`) prepočíta volania a čas na
100 úloh z nameraných hodnôt. Hodnoty zo skúšky mechanizmu na to použiť nemožno.
