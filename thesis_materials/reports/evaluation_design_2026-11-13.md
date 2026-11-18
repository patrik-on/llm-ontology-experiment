# Návrh aktuálnych evaluácií a runnerov

**Stav k 13. 11. 2026.** Metodický podklad do práce, odvodený z lokálnej
implementácie, konfigurácií, runbookov a pripravených behov. Nie je to report
dosiahnutej kvality modelov. Aktuálne pripravené behy majú **0 generovaní**.

## 1. Cieľ a výskumné otázky

Porovnávame päť spôsobov použitia lokálneho jazykového modelu pri generovaní
Java testov a refaktoringu. Zaujíma nás nielen syntaktická odpoveď, ale aj
vykonateľnosť, splnenie úlohy a opakovateľnosť hodnotenia.

- **VO1:** Aké rozdiely majú baseline, doménový fine-tuning, Single-RAG,
  MultiRAG a procesný skill pri rovnakých prípadoch a hodnotiacich pravidlách?
- **VO2:** V ktorej fáze vzniká neúspech: formát, zostavenie zdroja,
  kompilácia, vykonanie testov, nepokrytá cieľová metóda alebo chýbajúci refaktoring?
- **VO3:** Poskytuje retrieval použiteľný kontext a má procesný text skillu
  prínos aj bez nástrojov či opravných iterácií?
- **VO4:** Dokážeme ku každému výsledku doložiť presný vstup, konfiguráciu,
  modelovú odpoveď a dôkazy hodnotenia bez výberového vynechávania neúspechov?

Sú to otázky experimentu, nie vopred potvrdené hypotézy. Malý pilot slúži
predovšetkým na interpretovateľné porovnanie a kontrolu postupu.

## 2. Prečo práve dve matice

| Vlastnosť | Methods2Test testing | SWE refactoring |
|---|---|---|
| Runner | `scripts/benchmarks/run_testing_matrix.py` | `scripts/benchmarks/run_refactoring_matrix.py` |
| Orchestrácia | `src/llm_ontology/benchmarks/testing_matrix.py` | `src/llm_ontology/benchmarks/refactoring_matrix.py` |
| Konfigurácia | `configs/benchmarks/testing_matrix_v1.json` | `configs/benchmarks/refactoring_matrix_v1.json` |
| Jednotka | extrahovaná focal method a podporovaný kontext | jeden pôvodný produkčný Java súbor a cieľová operácia |
| Výstup modelu | JSON s dvoma telami testov do pevného scaffoldu | JSON s povolenou cestou a celým refaktorovaným súborom |
| Jadrový dôkaz | kompilácia, reálne JUnit vykonanie, focal invocation, JaCoCo | detekovaná cieľová operácia, build a stabilné regresné testy |

Rovnaký runner pre obe úlohy by zamieňal rozdielne kontrakty správnosti.
Naopak päť samostatných runnerov pre päť systémov by zvyšovalo riziko rozdielnych
vstupov a metriky. Preto každá úloha používa jednu maticu **prípad × systém**;
vnútri matice sú spoločné prípady, hodnotiteľ a pravidlá pokusov.

Tenké vstupné skripty iba zavolajú `main` príslušného modulu. Zdieľaná
infraštruktúra rieši atómové zápisy, zámky, účtovanie dispatchov, backendy,
retrieval, tokenové rozpočty a identity. Výber dát a hodnotenie zostávajú
špecifické pre úlohu. Interné helpery nie sú ďalšie eval protokoly.

## 3. Päť systémov a hranice férovosti

| Systém | Čo sa mení oproti baseline | Testing / refactoring |
|---|---|---|
| `qwen_base` | žiadny dodatočný kontext | lokálny Ollama Qwen2.5-Coder 7B |
| `ft_testing` / `ft_refactoring` | doménový LoRA adaptér cez HF/PEFT | `b2_testing_v2` / `b2_refactoring_v2` |
| `rag_single` | príklady z jednej existujúcej kolekcie | `mixed` / `refactoring_db` |
| `rag_multi` | spojené výsledky z dvoch kolekcií | `testing_db` + `refactoring_db`, existujúca fusion/RRF |
| `skills` | procesný text existujúceho taskového skillu | baseline + presné bajty príslušného `SKILL.md` |

Skill sa nevytvára ani neupravuje pre jednotlivé prípady. Používajú sa súbory
z `../si-context-eval/skills/{testing,refactoring}/SKILL.md`, ktoré sa kopírujú
a hashujú do runu. Nie je to agent, kombinácia skills+RAG/FT ani test AGENTS.
Rady skillu o iteráciách neoprávňujú model na ďalší pokus.

V rámci úlohy je spoločný viditeľný vstup, výstupný kontrakt, hodnotiteľ,
seed 42, deterministické nastavenie (Ollama temperature 0, HF greedy) a limit
jednej odpovede. Testing má 4096 výstupných tokenov, refactoring 8192 kvôli
celému súboru; oba kontext 32768. Nejde o dôkaz bitovej deterministickosti GPU.

FT beží cez HF NF4/raw výstup, ostatné cez Ollama Q4_K_M so schema-constrained
JSON. **Porovnávame systémy, nie čistý kauzálny efekt adaptéra.** Dlhší skill
nie je kontrolovaný rovnako dlhým placebo promptom. Single-RAG a MultiRAG sa
líšia aj zložením evidencie, nielen počtom kolekcií.

## 4. Methods2Test: výber, meranie a jeho dôvod

Používa sa oficiálny split **EVAL**; TEST zostáva rezervou. Selector ide
deterministicky poradím archívu, obmedzuje počet prípadov na projekt a vylučuje
predtým explorované ID, train/val projekty a známe normalizované zhody či
containment voči train/val a reálnym RAG dokumentom. Rich a corpus reprezentácia
musia súhlasiť. Neznáma historická lineage sa neoznačuje za dokázane čistú.

Prípad musí byť podporovaná verejná statická metóda s rekonštruovateľným
JDK-compatible kontextom. Pôvodný developer test musí pred generovaním
skompilovať, prejsť a cez inštrumentáciu preukázať volanie správneho JVM overloadu.
Tak oddeľujeme chybu modelu od prípadu, ktorý nefunguje už v hodnotiteľovi.
Referencia je evaluator-only; nikdy nejde do modelového promptu ani RAG indexu.

Model používa `testing-bodies-one-shot-v2`: dva neutrálne sloty testových tiel,
pevný scaffold a vyriešený nesúvisiaci príklad. Je to zníženie formátovej záťaže
a zjednotenie porovnania, nie test autonómnej tvorby celej testovej infraštruktúry.
Rovnaké zadanie dostane každý systém.

Hodnotenie rozlišuje platný JSON/schéma, zloženie Java zdroja, kompiláciu,
skutočne spustené testy, úspech triedy, volanie focal method, opakovanú stabilitu
a method/class line/branch coverage z JaCoCo. Dve vykonania sú **hodnotiteľské
repeats**, nie dve nové modelové generácie. Lexikálny výskyt assertion nie je
sám dôkaz správneho testu.

Coverage neúspešnej triedy je diagnostická, nie primárny úspech. Chýbajúce
meranie je `null` s dôvodom, branchless metóda má príslušnú metriku N/A.
Nulové pokrytie a neprítomné meranie nie sú tá istá vec.

**Čo z toho možno tvrdiť:** kvalita testov v dependency-filtered
extracted-method harnessi. **Čo nie:** build celého pôvodného projektu,
všeobecné odhaľovanie reálnych chýb alebo mutation score. V tomto protokole
nie je buggy revision ani mutation kampaň.

## 5. SWE refactoring: prečo operácia nestačí bez testov a naopak

Príprava vychádza z vopred zoradeného shortlistu datasetových prípadov.
Podporujeme iba single-file **Extract Method a Inline Method**; PMD je vylúčené.
Datasetový celý pôvodný súbor musí bajtovo súhlasiť so skutočným prvým parentom
developer commitu. Nejednoznačné overloady sa odmietajú.

Baseline a developer referencia musia prejsť buildom a dvoma vykonaniami
cieľovej regresnej sady. Referenčný súbor sa aplikuje do pôvodného parenta,
nie spolu so zmenenými testami alebo build súbormi developer commitu.
Kontroly overujú prijatie referencie, odmietnutie no-op, neplatnej Javy
a vopred určenej kompilovateľnej behaviorálnej mutácie. Mutácia je QA
hodnotiteľa, nie mutation score modelových výsledkov.

Model dostane celý pôvodný súbor, požadovanú operáciu a identitu cieľa.
RefactoringMiner **3.0.10** porovná pred/po a matcher vyžaduje správnu operáciu,
súbor, triedu, pôvodnú metódu a rozsah. Nestačí detegovať ľubovoľný refaktoring;
názov novej pomocnej metódy nemusí kopírovať referenciu.

Samotná detekcia nezaručuje zachovanie správania, preto kandidát musí aj
skompilovať a dvakrát prejsť skutočnými testmi. Samotný prechod testov zas
nestačí: nezmenený súbor by prešiel, ale nesplnil by operáciu. Kontrolujú sa
čerstvé Surefire XML, neprázdna sada vykonaných testov, zhodné identity/stavy
s baseline a zhodné skips; Maven exit code sám osebe nie je oracle.

Historické projekty používajú zaznamenané JDK 8/11/17 podľa potreby.
Kandidáti sa hodnotia v čerstvých archívoch parent commitu s Maven offline
po príprave závislostí. Neprepisuje sa používateľský checkout. Bežia
target-focused testy, nie deklarovane celý test suite každého projektu.

**Úspech znamená:** splnený kontrakt, skutočná požadovaná operácia,
kompilácia a stabilný prechod kontrolovaných testov. Nie je to formálny dôkaz
univerzálnej behaviorálnej ekvivalencie ani meranie všeobecnej kvality kódu.
Základný overlap audit nie je potvrdením repository-disjoint alebo
pretraining-unseen datasetu.

## 6. Životný cyklus a ochrana interpretácie

1. **Plán:** `--dry-run`, bez zápisu a modelových volaní. Nové behy majú
   default 100 prípadov × 5 systémov, najviac 500 generačných pokusov
   (od 18. 11. 2026; pôvodne 5 × 5 = 25).
2. **Príprava:** `--prepare-only`, validácia dát, referencií a hodnotiteľa,
   bez generovania odpovedí. Refactoring príprava môže stiahnuť verejný Git/Maven vstup.
3. **Freeze:** `--freeze-only`, uloženie skutočných promptov, skillu,
   retrieval evidencie a identít dát/zdrojov/modelov/indexov/nástrojov.
   Metadata/embedding volania sú možné, generovanie nie.
4. **Generovanie a hodnotenie:** príkaz bez režimového prepínača.
   Presný vstup sa nemení podľa už videných výsledkov.
5. **Resume/report:** rovnaké run ID overí identity; `--report-only`
   rekonštruuje report bez ďalších generácií. Refactoring má aj `--evaluate-only`.

Každá bunka má **jeden pokus, nula retries a nula repairs**. Durable dispatch
marker vzniká pred volaním, preto sa aj prerušené/neznáme odoslanie započítava
do limitu a automaticky sa neopakuje. Infraštruktúrna anomália pozastaví rameno;
bežná neplatná modelová odpoveď zostáva neúspešnou bunkou. Nové ID nie je
spôsob ako po zhliadnutí chýb potichu nahradiť zlý výsledok.

Obe matice zdieľajú GPU zámok a sériové vlastníctvo lokálnych backendov.
Tým obmedzujeme konflikty pamäte, nie experimentálnu neistotu malého datasetu.
Zdrojové/nástrojové/modelové hashe a freeze sa pri pokračovaní kontrolujú.
Dokončené výsledky sa nikdy spätne nepodpisujú novým kódom; zmenený experiment
potrebuje samostatnú identitu. QA kontrola procesu nie je OS security sandbox.

## 7. Výsledky, menovatele a analýza

Kanonický koreň je `artifacts/evaluation/runs/<run-id>/`: plán, výber a QA,
presné frozen prompty, dispatch, raw odpovede, Java kandidáti, testové XML,
coverage/detektor, chyby a `reports/aggregate.json` + `reports/summary.md`.

Reportovať treba N plánovaných prípadov, počet skutočných pokusov,
úspechy/neúspechy a pending/unresolved osobitne. V testing agregáciách sa pri
jednotlivých metrikách uvádza ich vlastný menovateľ a unknown; nevydávať ho
automaticky za všetky plánované bunky. Pri refactoringu plánované prípady
zostávajú v menovateli ramena, nedokončenosť je explicitná. Nezavolaná bunka
nie je passing ani rozhodnuté modelové zlyhanie. Neúspešná odpoveď sa nesmie
vynechať len preto, že nedošla až po vykonanie testov.

Párové porovnania používajú **tie isté prípady**: uviesť, kde uspeli oba
systémy, iba jeden alebo ani jeden, nielen priemer. Pri piatich systémoch je
desať dvojíc. Coverage porovnávať iba podľa explicitne platných meraní
a rovnakých cieľov; úspešnosť reportovať popri nej, aby sa nestratil vplyv
zlyhaní. Od 18. 11. 2026 reporty pridávajú exaktné párové testy: McNemar na
nesúhlasných pároch pre pass/fail (testing class pass, refactoring structural
success) a Wilcoxon signed-rank pre coverage credit, s Holmovou korekciou cez
desať dvojíc každej metriky. Pri 100 prípadoch má McNemar rozumnú silu na
rozdiely okolo 10–15 percentuálnych bodov, ak sú nesúhlasné páry dostatočne
časté. P-hodnoty sú podmienené vybranými prípadmi (convenience výber, najviac
10 prípadov z jedného projektu), nie dôkaz populačnej reprezentatívnosti.

## 8. Aktuálny stav a čo ešte nemožno uzavrieť

| Pripravený beh | Prípady | Frozen prompty | Generovania |
|---|---:|---:|---:|
| `testing-matrix-preparation-check-20261113` | 1 | 5 | 0 |
| `refactoring-ready-v2-clean-20261113` | 5 | 25 | 0 |

Prvý je minimálna príprava jedného prípadu, nie predvolený päťprípadový
experiment. Implementačné overenie po konsolidácii uvádzalo **288 passed,
2 skipped**; sú to softvérové kontroly, nie úspechy modelov.
Z týchto príprav zatiaľ nemožno určiť víťaza, prínos RAG, FT ani skillov.

Hlavné limity: malá nenáhodná a dependency-filtered vzorka, projektové
zhlukovanie, jeden generačný pokus, odlišné backendy/kvantizácie, rôzne dĺžky
kontextov, neznáme historické pretraining prekryvy a neúplnosť testových
oracles. V práci preto oddeliť návrh systému, overenie hodnotiteľa,
exploratívne modelové merania a prípadné širšie potvrdenie.

## 9. Lokálne zdroje a súvis s handcrafted experimentom

- [Testing runbook](../../docs/evaluation/testing_matrix_v1.md),
  [refactoring runbook](../../docs/evaluation/refactoring_matrix_v1.md),
  [overenie implementácie](../../docs/evaluation/validation_2026-11-13.md).
- [Konfigurácia testing](../../configs/benchmarks/testing_matrix_v1.json),
  [konfigurácia refactoring](../../configs/benchmarks/refactoring_matrix_v1.json).
- [Mapa implementácie](../../docs/architecture/project_map.md),
  [SWE overlap audit](../../docs/datasets/swe_refactor_basic_overlap_2026-11-13.md).
- [Handcrafted archív](../handcrafted_skills/README.md): motivácia pre procesný
  kontext a poznatky o menovateľoch/gradere. Tamojšie agentové protokoly,
  datasety a výsledky sa **nezlučujú** s dnešnými jednokrokovými maticami.

Report opisuje lokálne implementovaný návrh; nie je novým rešeršným tvrdením
o aktuálnom stave externých benchmarkov alebo ich dostupnosti.
