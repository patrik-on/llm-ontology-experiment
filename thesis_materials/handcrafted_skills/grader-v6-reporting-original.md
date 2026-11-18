# Hodnotiaci profil, inventár pokusov a reportovanie v6

Dátum: **21. 10. 2026**, Europe/Bratislava. Úloha **3C**. Hodnotiteľ **`v6-dev.3`**, formát reportu **`experiment-report-v1`**, pravidlá inventára **`attempt-outcomes-v1`**, rozhodovanie výsledku grade **`grade-outcomes-v1`**. Dataset zostáva `eval-v5-base` = `563f27d248e2a505a368f131a21fee315631dbaa`.

Výsledok: explicitný profil prechádza CLI → suite/prepare → grade → report. Kompletná sada má **219/219 úspešných regresných testov**. Tri nové ručné overenia cez reálny Maven/CLI splnili vopred zapísané očakávania: **success, model_failure, review_required**, bez modelového volania. Nový read-only historický report zahŕňa **240/240 pokusov**, **94 úspechov**, **146 modelových neúspechov**, z nich **13 bez kandidáta**. GPT-OSS combined/testing má primárny výsledok **7/12**, namiesto starého podmieneného 7/9.

## Východiskový stav a zachovanie práce

Repozitár: `C:\Users\patri\OneDrive\Dokumenty\GitHub\si-context-eval`, vetva `main`, HEAD `57ce66062f53ed5366741a8add866e136e8f9f2c`. Susedný `llm-ontology-experiment` nebol menený. Pred úpravami už existovali necommitované zmeny README, agenta, CLI, graderu a suite, agent-v2, audity a kontroly 3A/3B. Ich stav nebol resetovaný ani commitnutý.

Vstupné závery: [pilotný audit](pilot-v5-audit.md), [počítanie testov 3A](grader-v6-test-execution.md), [objective profil 3B](grader-v6-refactoring-objective.md). Kontrakty a kandidáti predchádzajúcich etáp ostali nezmenené. Ani historickí kandidáti, skilly, projektové `AGENTS.md`, task manifesty, subject projekty, reference a oracles neboli upravované alebo prehodnocované. Nový Java kandidát je samostatná kontrolná fixture.

Na začiatku bola uložená SHA-256 inventúra **15 175 existujúcich súborov mimo `.git/`**, vrátane **14 894 súborov v `runs/`**. Zálohy deviatich upravovaných existujúcich zdrojových súborov zachovávajú aj predošlé necommitované znenie. Finálne overenie a zdrojové hashe: [task preservation](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/task-3c-preservation.json), [zálohy a vstupný inventár](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/task-3c/). Žiadny commit, push ani pohyb tagu sa nevykonal.

## Použitie profilu a preflight

`--profile` naďalej vyberá experimentálnu podmienku. Nový `--grader-profile` vyberá pravidlá hodnotenia:

- `legacy`: pôvodný štruktúrny kontrakt; pri vynechaní voľby sa aj toto použitie explicitne zapíše a zobrazí;
- `r-api-quantity-objective-v1`: objective kontrakt 3B, cez bežné CLI/suite povolený výhradne pre refactoring prípad `r-api-quantity`.

Príklady príkazov z koreňa repozitára, spustené cez WSL Python; prvý príklad je dry-run:

```sh
python3 -B -m evaluation.cli run-suite --profile clean-refactor --case r-api-quantity --protocol agent-v2 --model qwen2.5-coder:7b --grader-profile r-api-quantity-objective-v1 --dry-run
python3 -B -m evaluation.cli prepare --case r-api-quantity --variant none --protocol agent --run-dir runs/manual/NEW-RUN --grader-profile r-api-quantity-objective-v1
python3 -B -m evaluation.cli submit --case r-api-quantity --run-dir runs/manual/NEW-RUN --source-file /path/to/OrderApi.java --approach other --model-id EXTERNAL-MODEL --provider EXTERNAL-PIPELINE --grader-profile r-api-quantity-objective-v1
python3 -B -m evaluation.cli grade --case r-api-quantity --run-dir runs/manual/NEW-RUN --grader-profile r-api-quantity-objective-v1 --maven /home/patrik/.local/bin/mvn
python3 -B -m evaluation.cli report --runs-root runs/experiments --output runs/reports/NEW-REPORT.json
```

Príklady `NEW-RUN`/`NEW-REPORT` nie sú modelové experimenty vykonané touto úlohou. Pri ručných kontrolách bol navyše použitý `prepare --experiment-kind verification`, aby nevstupovali do modelových mier.

[grader_profiles.py](../../evaluation/grader_profiles.py) vykonáva preflight pred runtime discovery, dotazom na model aj prípravou workspace. Suite najprv overí **všetky vybrané prípady**; napríklad objective profil nad celým `clean-refactor` bez obmedzenia na `r-api-quantity` sa odmietne pred začatím. Profil uložený pri príprave musí súhlasiť s ďalšími CLI krokmi. Chýbajúci historický profil sa pri pokračovaní starého workspace považuje za legacy; požiadavka na objective vyžaduje novú prípravu. Prepnutie na legacy sa nevykonáva potichu.

Dry-run plán, `run.json`, `suite.json`, `generation.json` a `grade.json` explicitne nesú profil. Nové run/grade/suite záznamy navyše obsahujú identitu kontraktu a hodnotiteľa. Suite odovzdáva profil ako argument `core.grade(..., profile=...)`. Historická kompatibilita interného core API z 3B zostáva zachovaná; sprísnenie podporovaných kombinácií platí pre nové CLI/suite vstupy.

## Výsledkové stavy a dôkazy začatia

[outcomes.py](../../evaluation/outcomes.py) spoločne klasifikuje grade výsledok. [reporting.py](../../evaluation/reporting.py) skladá dôkazy z dostupných záznamov, bez ich prepisovania. `success` je `true` iba pri `success`, `false` iba pri rozhodnutom `model_failure`; ostatné stavy ponechávajú `null`.

| Stav | Význam a rozhodujúci dôkaz |
|---|---|
| `success` | Dostupné hodnotenie preukazuje splnenie aktívnych brán. Historický úspech zostáva úspechom podľa zaznamenaných pravidiel. |
| `model_failure` | Doložený neplatný výstup, vyčerpanie rozpočtu bez kandidáta, kandidátom spôsobená chyba kompilácie, vykonaný neúspešný referenčný/behaviorálny test alebo nesplnený kontrakt. |
| `review_required` | Správne technicky spracovaný kandidát je mimo rozhodovacieho kontraktu objective analyzátora; samotný beh nemá preukázané kompilačné/behaviorálne zlyhanie. |
| `technical_error` | Doložený chýbajúci nástroj, problém prostredia, timeout Maven alebo technická nedostupnosť/pád analyzátora. Môže vzniknúť pred začatím modelu. |
| `unsupported` | Nepodporovaná kombinácia profilu a tasku; preflight zabráni modelovému volaniu. |
| `incomplete` | Chýba spoľahlivý terminálny výsledok, príčina je neznáma alebo si záznamy odporujú. Chýbajúci grade nestačí na určenie zlyhania. |
| `not_started` | Samostatne evidovaný naplánovaný/pripravený pokus bez dôkazu začatia modelu a bez iného doloženého terminálneho stavu. |

**Používateľské spresnenie tejto úlohy:** pri preukázanom kompilačnom alebo behaviorálnom zlyhaní je hlavný stav `model_failure`, aj keď `refactoring_objective.status=review_required`. Celý objective výsledok sa zachová samostatne v grade. To isté platí pri odvodenej historickej klasifikácii. Očakávané zlyhanie buggy programu v testing úlohe sa nepovažuje za zlyhanie kandidáta; naďalej ide o úspešné odhalenie chyby, ak prešli ostatné brány. Parser outage je technický stav, validný nerozhodnuteľný Java tvar je review.

Nový [attempt.json](../../evaluation/attempts.py) rozlišuje prípravu od skutočného pokusu. Po príprave má `model_started=false`. Agent a one-shot adaptér zaznačia začatie bezprostredne pred prvou generačnou požiadavkou na providera, až po bootstrap/baseline krokoch. Záznam uchováva identitu modelu/providera a parametre aj pri neskoršom zlyhaní bez kandidáta. Pri externom modelovom `submit` ide o deklarované externé odovzdanie; nevymýšľa sa čas skoršieho provider volania. Ručné `verification` a `control` submit kroky modelový štart neoznačujú.

Historický čítač hľadá aj generation/error/usage/provider záznamy a výsledky suite. Počiatočný prompt, samotný workspace ani všeobecné `phase=generation` nepreukazujú modelový štart. Pri nedostatočných dôkazoch je `model_started=null` a `start_unknown=true`; orphan error si nevymýšľa ani plán. Každá odvodená klasifikácia má `reasons` s cestou a poľom zdrojového záznamu. Rozpory sa zapisujú do `conflicts` so zdrojovými cestami a vedú na `incomplete`.

## Inventár, menovatele a porovnateľnosť

Čítač inventarizuje plány `suite.json` aj `run.json`, `generation.json`, `error.json`, `grade.json`, `attempt.json`, `agent_usage.json` a provider artefakty. Canonical adresár/prípad sa započíta raz; explicitné `attempt_id` umožní deduplikáciu naprieč adresármi. Rovnaký hash kandidáta neodstraňuje opakované pokusy. Rozporné duplicity zostávajú jeden nerozhodnutý pokus. Kalibrácie, kontrolné fixture, pracovné/exportované kópie a provenance sa predvolene vylučujú. `--include-verification` zobrazí samostatnú verification kohortu, ktorej menovateľ modelových pokusov zostáva nula.

Report osobitne uvádza `planned`, `started`, `not_started`, `start_unknown`, `counts` podľa stavov a `unresolved_started`. Konečná `model_success_rate`/`success_rate` je číselná iba pre uzavretú modelovú skupinu. Pri review, technickej chybe alebo incomplete medzi začatými pokusmi zostáva `null`; report stále ukáže potvrdené úspechy zo všetkých začatých pokusov. Nezačaté a nejasne začaté položky bránia označeniu celej plánovanej skupiny za uzavretú. `conditional_decided_success_rate` je explicitne podmienená na rozhodnuté modelové pokusy.

Príklady výsledkov podľa overených pravidiel:

| Skupina | Potvrdené úspechy / začaté | Nerozhodnuté začaté | Konečná miera | Podmienená miera medzi rozhodnutými |
|---|---:|---:|---:|---:|
| 7 success + 2 graded failure + 3 generation failure | 7/12 | 0 | 7/12 | 7/12 |
| 1 success + 1 model_failure + 1 review + 1 technical | 1/4 | 2 | `null`, neúplná | 1/2 |
| Iba pripravený workspace | 0/0 | 0 | `null` | `null` |
| Tri ručné overenia tejto etapy | 0/0 modelových | 0 modelových | `null` | `null` |

Primárne `groups` predstavujú samostatné plánované suite kohorty, rozdelené podľa vetvy/podmienky/druhu pokusu. Dve suite sa automaticky nezlučujú. V rámci suite sa porovnajú všetky známe identity a parametre; pri ich rozpore sa vytvoria oddelené neporovnateľné časti s neuzavretou mierou. Samostatné pokusy sa zoskupujú podľa úplnej známej identity. Sledujú sa model a digest, provider, protokol a fingerprint, dataset commit a task manifest, profil/verzia/implementácia hodnotiteľa, hashe skillov/kontextov, sampling parametre, thinking, rozpočty, seedy a validačné limity.

Chýbajúca historická hodnota zostáva `<unknown>`. `metadata_coverage` pri každej skupine uvádza známe a neznáme záznamy. Riedke artefakty neodstraňujú generačné neúspechy z plánovanej kohorty; zároveň sa im nekopírujú parametre od susedných pokusov. `identity_groups` sú prísne diagnostické rezy, nie náhradný menovateľ primárneho výsledku: nesmú zmeniť 7/12 na 7/9. Celkové `totals` sú inventár všetkých podmienok, nie dôkaz ich vzájomnej experimentálnej porovnateľnosti.

Historické legacy automatické refaktoringové úspechy sú explicitne označené `legacy_automatic_refactoring_success`. Známemu v5 hash-u core možno priradiť legacy profil s dôkazom; chýbajúcu verziu hodnotiteľa ani nový objective výsledok z neho čítač nevyrába. Nový reporter má vlastné časové a implementačné metadáta, oddelené od identity historického hodnotiteľa. Staré záznamy ani chýbajúce `skipped`/`executed` polia sa nedopĺňajú.

## Overenie a reprodukcia

Príkazy nižšie boli vykonané v Ubuntu WSL, z `/mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/si-context-eval`. Python **3.12.3**, Maven **3.9.16**, JDK **17.0.20.1**; [presné prostredie](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/environment.json) a [zdrojová snímka](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/source-sha256.json) obsahujú konkrétne príkazy, výstupy a hashe. Maven použil izolovanú kópiu existujúcej cache v novom výsledkovom adresári.

```sh
python3 -B -m unittest discover -s evaluation/tests -v
python3 -B -m evaluation.grader_controls_v6_reporting --check
python3 -B -m evaluation.grader_controls_v6_reporting --maven /home/patrik/.local/bin/mvn --seed-maven-repo runs/cache/maven
```

Prvý úplný unit beh prešiel **218/218**, po doplnení regresie rozporných explicitných ID prešiel **219/219**. Záverečná kontrola našla ešte chýbajúce diagnostické príznaky vo vnorenom `suite.outcome_summary`; doplnili sa `has_grade`/`generation_failure` a assertions na zhodné počty 9 grade + 3 generation failures. Finálny úplný beh znovu prešiel **219/219**. [Unit logy a príkazy](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/task-3c/development-verification/) zachovávajú aj vývojové overenia. Nové regresie pokrývajú všetky požadované stavy, príklad 7/12, no-candidate budget failure, null review, baseline chybu pred provider volaním, pripravený/neznámy štart, chýbajúce/rozporné záznamy, deduplikáciu, vylúčenie kalibrácií a kópií, rozdielne profily/parametre a odmietnutie celej nepodporovanej suite bez modelového volania. Dve staršie reportové očakávania boli upravené na nové pravidlá; pôvodná trieda suite regresií zostala zachovaná.

Všetky štyri reálne CLI dry-runy použili prvý príkaz v časti používania, so zmenou `--profile` na `clean-refactor`, `refactor`, `agents-refactor`, `combined-refactor`. Každý plán obsahuje iba `r-api-quantity`, príslušný variant a explicitný objective profil; plánovaný run adresár nevznikol. [Plány, stdout, stderr a presné argv](../../runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/dry-run/).

[Nový zmrazený manifest](../../evaluation/controls_v6_reporting/manifest.json) bol uložený pred meraním; jeho hash `44523df613c88fbe3b82e3cad42246909cf18e1f30841ee6df4fb76c19586434` sa overil preflightom. Pôvodný objektívny kontrakt 3B sa nemenil. Nová kontrola `R-review` pridáva do správneho riešenia podmienku nad `sku`, ktorej obe vetvy volajú tú istú službu s tými istými argumentmi. Odstránenie jediného pridaného bloku obnoví pozitívny zdroj bajtovo. Tým sa správnosť odvodenia posudzuje nezávisle od analyzátora; reálne behaviorálne testy ho dopĺňajú.

| Kontrola | Pôvod kandidáta | Behaviorálne testy | Objective | CLI grade kód | Grade/report úspech | Modelové štarty |
|---|---|---:|---|---:|---|---:|
| `P-positive` | Nezmenený 3B `A-direct` | 13/13, 0 skipped | pass | 0 | success / `true` | 0 |
| `N-negative` | Nezmenený 3B `D-ignored-result` | 13/13, 0 skipped | fail | 1 | model_failure / `false` | 0 |
| `R-review` | Nová samostatná fixture | 13/13, 0 skipped | review_required | 2 | review_required / `null` | 0 |

Výsledky: **3 platné kontroly, 0 nesúladov, 0 technických chýb; spúšťač exit 0**. [Súhrn](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/summary.json), [CLI kroky](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/cli/), [grade a surové Maven/XML dôkazy](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/attempts/), [report s verification](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/reports/verification.json), [predvolený report](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/reports/default.json). Predvolený report kontroly vynechal; explicitná verification kohorta má po jednom výsledku každého očakávaného stavu, pričom modelový menovateľ aj počet modelových pokusov zostali nula.

Spúšťač zaznamenáva reálne CLI `prepare → submit → grade → report`. Konkrétne argv vrátane zdrojov, Maven proxy a cache sú pri každom kroku v `command.json`. Zdrojová snímka, Git bundle, execution plan, zmrazený manifest a ochranný inventár sú v [provenance](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/). Žiadny historický modelový kandidát sa počas overenia neprehodnotil; pozitívna a negatívna kontrola sú existujúce ručne pripravené fixtures z 3B.

Posledná diagnostická úprava suite vznikla po Maven overení. [Finálna zdrojová snímka](../../runs/calibration/grader-controls-v6-reporting/20261021T142718Z-6fa20aba/provenance/task-3c/final-source-sha256.json) ju uchováva oddelene od meranej snímky: zmenili sa iba `suite.py` a jeho nový testovací modul. Všetkých deväť súborov identity graderu aj CLI prepare/submit/grade/report zostalo bajtovo zhodných s meraním; ich hashová zhoda je v task preservation. Finálne unit testy a všetky štyri dry-runy boli vykonané po tejto úprave, s aktuálnym fingerprintom. Maven merania nebolo potrebné opakovať kvôli doplneniu diagnostických počítadiel suite.

## Nový historický report

Presný read-only príkaz:

```sh
python3 -B -m evaluation.cli report --runs-root runs --output runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/historical-report.json
```

[Nový report](../../runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/historical-report.json), [príkaz a logy](../../runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/historical-report-command/), [automatické overenie súčtov a dry-runov](../../runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/verification-summary.json). Zahŕňa **20 samostatných suite kohort**, 240 plánovaných a začatých pokusov, 227 grade výsledkov a 13 doložených generačných neúspechov. Žiadna lokálna položka nemá neurčený/technický stav alebo rozpor; toto tvrdenie platí len pre dostupné záznamy. **63 úspešných refaktoringov je legacy automatických úspechov**, nie objective overenie.

| Porovnateľná štvorica z auditu | none | skill | agents | combined |
|---|---:|---:|---:|---:|
| Qwen, pôvodný agent, refactoring | 8/12 | 8/12 | 8/12 | 7/12 |
| Qwen, pôvodný agent, testing | 2/12 | 2/12 | 0/12 | 1/12 |
| Qwen, agent-v2, refactoring | 7/12 | 6/12 | 9/12 | 10/12 |
| Qwen, agent-v2, testing | 2/12 | 3/12 | 1/12 | 2/12 |
| GPT-OSS, agent-v2, testing | 4/12 | 3/12 | 4/12 | 7/12 |

Súčty sa s pilotným auditom zhodujú: **94 + 133 + 13 = 240**. Nový report posledné dve položky združuje ako 146 rozhodnutých modelových neúspechov, pričom 13 generačných neúspechov uvádza aj osobitne. Oproti starému grade-only reportu sa mení menovateľ GPT-OSS: `4/10 → 4/12`, `3/8 → 3/12`, `4/8 → 4/12`, `7/9 → 7/12`. Počet úspechov sa nemení. Podmienenie starých mier bolo na existenciu hodnotiteľného kandidáta; nová podmienená metrika má výslovne inú definíciu, rozhodnuté modelové pokusy.

Tieto štvorice sa navzájom nespájajú do opakovaní rovnakého experimentu. Rozdiely protokolu, implementačných fingerprintov, modelov a thinking zostávajú zaznamenané. Neznáme historické metadáta zostali neznáme; napríklad tri generačné neúspechy C combined nemajú generation provider/parametre v rovnakom rozsahu ako deväť odovzdaných kandidátov. Report uvádza pokrytie metadát a zachováva všetkých dvanásť členov pôvodného plánu.

## Zmenené súbory a hranice opravy

Upravených deväť existujúcich súborov:

- [core.py](../../evaluation/core.py), [evaluator_version.py](../../evaluation/evaluator_version.py): explicitná identita, ukladanie profilov a jednotné rozhodnutie; grader zvýšený z dev.2 na **dev.3**, keďže sa mení priorita kompilačného/behaviorálneho zlyhania voči review.
- [cli.py](../../evaluation/cli.py), [suite.py](../../evaluation/suite.py): výber a preflight, prenos profilu, nové stavy a report; odmietnutie prepisu existujúceho grade/report výstupu.
- [agent.py](../../evaluation/agent.py), [agent_v2.py](../../evaluation/agent_v2.py), [submission.py](../../evaluation/submission.py): záznam skutočného provider štartu a parametrov; nový fingerprint agenta odlišuje zmenenú podpornú implementáciu.
- [test_suite_v2.py](../../evaluation/tests/test_suite_v2.py), [test_model_selection.py](../../evaluation/tests/test_model_selection.py): aktualizované reportové očakávania bez vymyslených historických defaultov.

Pridané sú [grader_profiles.py](../../evaluation/grader_profiles.py), [attempts.py](../../evaluation/attempts.py), [outcomes.py](../../evaluation/outcomes.py), [reporting.py](../../evaluation/reporting.py), [grader_controls_v6_reporting.py](../../evaluation/grader_controls_v6_reporting.py), [kontrolný manifest, README a jediný nový Java kandidát](../../evaluation/controls_v6_reporting/), šesť nových testovacích modulov `test_attempt_markers.py`, `test_outcomes.py`, `test_reporting.py`, `test_cli_grader_profiles.py`, `test_suite_reporting.py`, `test_cli_reporting_controls.py` a tento dokument. Výsledky/logy ostávajú v nových ignorovaných adresároch `runs/`; do dokumentácie sa nekopírujú transkripty ani dátové stromy.

Obmedzenia:

- Objective preflight v CLI/suite podporuje iba `r-api-quantity`. Nerozhodnuteľné platné tvary žiadajú manuálne review. Rozšírenie na ďalšie tasky táto etapa nerobí.
- Report odvodzuje stav z uložených dôkazov a rozpoznaných diagnostík; neobnoví stratené logy ani pôvodnú príčinu neznámeho prerušenia. Rozpory rieši explicitnou neistotou.
- Provider marker dokazuje prekročenie hranice odoslania požiadavky, nie dokončenie inferencie na vzdialenom serveri. Externé modelové odovzdanie je deklarácia externého pokusu, nemá doložený lokálny štart inferencie.
- Behaviorálna správnosť kontrol je podopretá existujúcimi 13 testmi a pri review aj jednoduchým nezávislým odvodením zdroja; nejde o formálny dôkaz ekvivalencie ľubovoľného programu.
- Legacy syntaktický profil má naďalej známu slabinu `R-empty-helpers`. Objective profil pre jediný podporovaný task rieši kontrakt 3B; historické legacy úspechy sa tým spätne neopravujú. Pôvodné kontrakty a ich historické výsledky zostávajú zachované.

Úloha 3C je uzavretá týmto overením. Ďalšie objective tasky a nové modelové experimenty neboli spustené.
