# Návrh experimentu: opravná slučka bez ontológie (C) a s ontológiou a SHACL (D)

Dátum: 23. 11. 2026. Stav: **návrh**, nič z toho ešte nie je implementované ani spustené.
Podklad: repo na commite `ee37e6b`, finálne behy `testing-matrix-20261122-rag2` a
`refactoring-matrix-20261121` (8 ramien × 100 prípadov, jeden pokus na bunku) a analýzy
v `thesis_materials/2026-11-2*`.

Súbory v tomto priečinku:

| Súbor | Obsah |
|---|---|
| `README.md` | tento návrh |
| `shapes_testing.ttl` | SHACL tvary T1–T4 pre úlohu testing |
| `shapes_refactoring.ttl` | SHACL tvary R1–R4 pre úlohu refactoring |
| `priklady/` | ručne zostavené dátové grafy a skript, ktorý tvary overí cez pySHACL (8 a 13 očakávaných porušení) |

---

## 0. Zhrnutie

Doterajšia ontológia (`onto_project`) nepomohla, lebo bola prepisom kódu, ktorý model už videl v
prompte. Vznikala z jedného dodaného súboru (tree-sitter → rdflib, 9 tried TBoxu), do promptu išla ako
krátky blok a nič s ňou ďalej nekontrolovalo výstup. Nový experiment mení dve veci naraz a obe
porovnáva proti férovej kontrole:

1. **Slučka s nástrojmi** (rameno C): model vygeneruje odpoveď, nástroj ju overí (javac + JUnit pri
   testoch, RefactoringMiner pri refaktoringu), konkrétna chybová správa ide späť modelu.
   Najviac 2 opravy, teda spolu najviac 3 pokusy.
2. **Tá istá slučka plus ontológia, ktorá vie viac než prompt, a SHACL obmedzenia** (rameno D):
   fakty z classpath alebo z celého projektu (signatúry, konštruktory, hierarchia, meniteľnosť,
   viditeľnosť) a 8 SHACL tvarov odvodených z nameraných chýb. Porušenia sa pridajú k spätnej väzbe
   nástroja.

Porovnanie D vs C izoluje prínos ontológie v rovnakej slučke. Pokus 1 v D sa od pokusu 1 v C líši iba
ontologickým blokom, takže z toho istého behu sa dá oddeliť efekt bloku (pokus 1) od efektu SHACL
spätnej väzby (pokusy 2 a 3).

| Rameno | Model (backend) | Pokus 1 | Pokusy 2–3 |
|---|---|---|---|
| `c_base` | Qwen2.5-Coder-7B, Ollama Q4_K_M, structured JSON (ako `qwen_base`) | prompt `qwen_base` bez zmeny | + predošlá odpoveď + správa nástroja |
| `d_base` | to isté | prompt `qwen_base` + nový ontologický blok | + predošlá odpoveď + správa nástroja + porušenia SHACL |
V texte ďalej je C = `c_base` a D = `d_base`. Nič sa netrénuje a FT model sa v tomto experimente
nepoužíva (časť 3). C a D bežia na **presne tých istých 100 prípadoch** ako 8 doterajších ramien,
s tým istým modelom a dekódovaním, takže sa dajú párovo porovnať aj s nimi (časť 11.3). Doterajší
eval s 8 ramenami sa znova nespúšťa, jeho výsledky sú referencia.

---

## 1. Výskumné otázky a hypotézy

**VO-C/D.** Zvýši ontológia projektových faktov so SHACL obmedzeniami úspešnosť a efektivitu
iteratívnej opravy oproti rovnakej slučke, ktorá dostáva iba výstup nástrojov?

Predregistrované hypotézy (smer je určený vopred, testuje sa obojstranne):

| ID | Hypotéza | Metrika | Test |
|---|---|---|---|
| H1 | D má vyššiu konečnú úspešnosť než C | úspech po ≤ 3 pokusoch (S@3) | exaktný McNemar, Holm cez 2 primárne páry (testing, refactoring) |
| H2 | D potrebuje menej volaní modelu | počet volaní na prípad (1–3) | Wilcoxon signed-rank (párový) |
| H3 | po spätnej väzbe D zostane menej porušení pravidiel | bunky s ≥ 1 porušením v poslednom pokuse | McNemar, opisne aj po pravidlách |
| H4 | samotný nový blok (bez spätnej väzby) zmení úspešnosť pokusu 1 | S@1 | McNemar, sekundárne |

Sekundárna otázka (opisná, ale párová na rovnakom backende): koľko pridáva samotná slučka
(`c_base` S@3 vs `qwen_base` single-shot)?

---

## 2. Čo ostáva fixné

Nové behy musia byť porovnateľné s finálnymi behmi. Preto sa nemení nič z tohto:

| Položka | Hodnota (zo zmrazených plánov) |
|---|---|
| Prípady | presne 100 ID z `selection.json` behu `testing-matrix-20261122-rag2`, resp. 100 z `refactoring-matrix-20261121` (rovnaké poradie, overené hashom `case.json` / `before_sha256`) |
| Model | Ollama `qwen2.5-coder:7b` s rovnakým digestom (`generation_model_digest`), HF model a adaptéry s rovnakými SHA-256 (`arm_hf_identity`) |
| Dekódovanie | temperature 0, top_p 0.9, seed 42, `max_new_tokens` 4096, kontext 32768 (testing); refactoring podľa `refactoring_matrix_v1.json` |
| Výstupný kontrakt | testing: dve telá do pevného scaffoldu (`testing-bodies-one-shot-v2`), refactoring: JSON `FileAnswer` |
| Konečné hodnotenie | testing: `methods2test_execution.run` (review, 2 opakovania, JaCoCo) iba na poslednom pokuse; refactoring: `refactoring_structural.evaluate`, pri SWE `refactoring_execution.evaluate` |
| Štatistika | `benchmarks/paired_tests.py` (`mcnemar_exact`, `wilcoxon_signed_rank`, `holm`), paired bootstrap ako v `deep_analysis.py` |

Pravidlo z `AGENTS.md` „jeden pokus na bunku, žiadne opravy“ platí pre obe matice a ostáva. Slučka je
**samostatný protokol** (`repair_loop_cd_v1`) s vlastným runnerom a run ID. Pri implementácii treba
`AGENTS.md` doplniť o tretí runner a o to, že limit 3 pokusov platí len preň.

---

## 3. Ramená modelu

- **`qwen_base` (jediný model).** Najväčší priestor na zlepšenie: v testingu 22/100, z toho 47 zlyhaní na
  assertion a 18 nevyvážených tiel; v refactoringu 60/100, pričom 26 je `checks_failed`
  a 13 neplatná Java.
- **FT sa nepoužije.** Experiment má iba dve ramená, C a D, obe na čistom Qwene cez Ollamu. Tak sú
  na rovnakom backende ako `qwen_base`, `onto_project`, `skills`, `skills_onto` a `rag_single` a dajú
  sa s nimi párovo porovnať. S FT ramenami (HF NF4) je porovnanie iba opisné, rovnako ako doteraz.
  Variant slučky s adaptérom `b2_*_v3` by bol možné rozšírenie, ale nie je súčasťou tohto návrhu.

---

## 4. Slučka

### 4.1 Algoritmus jednej bunky (prípad × rameno)

```
pokus k = 1
prompt_1 = zmrazený prompt ramena (C: rovnaký ako qwen_base, D: + blok v2)
opakuj:
    odpoveď_k = generuj(prompt_k)                       # 1 volanie modelu, ledger počíta rozpočet
    kontrola_k = nástroj(odpoveď_k)                     # časť 4.2, bez gold výstupu a skrytých testov
    shacl_k = validuj(fakty(odpoveď_k) ∪ ontológia)     # D: ide do spätnej väzby; C: iba tieňové meranie
    ak kontrola_k == úspech alebo k == 3: koniec
    spätná_väzba_k = formátuj(kontrola_k [, shacl_k ak D])
    prompt_{k+1} = prompt_1 + predošlá odpoveď_k + spätná_väzba_k
    k = k + 1
konečné hodnotenie = existujúci scorer na odpovedi posledného pokusu
```

Rozhodnutia:

- **Stop iba podľa nástroja.** SHACL nikdy nepredĺži slučku: ak nástroj hlási úspech, bunka končí aj
  s porušeniami. Obe ramená tak majú rovnaký rozpočet aj rovnaké stop kritérium.
- **Markovovský prompt.** Pokus k+1 vidí pôvodný prompt, poslednú odpoveď a jej spätnú väzbu, nie
  celú históriu. Dĺžka promptu tak ostáva ohraničená (≤ pôvodný + 2 × výstup + 1 500 tokenov).
- **Neúspech výstupu je tiež spätná väzba.** Nevalidný JSON, nevyvážené telo alebo zlá `file_path`
  sa vrátia ako chyba a spotrebujú pokus. Infra chyba (Ollama, timeout JVM, pád RefactoringMinera)
  slučku zastaví a bunka ostane `unresolved`, rovnako ako v maticiach.
- **Pokus 1 sa generuje znova, nie preberá.** Pri temperature 0 a rovnakom digeste by mal byť
  bajtovo zhodný s výstupom `qwen_base` z finálneho behu. Zhodu meria pilot (časť 13).
  Prevzatím by sa ušetrilo 100 volaní na rameno, ale stratila by sa kontrola determinizmu.

### 4.2 Kontrola nástrojom počas slučky

**Testing:**

1. `parse_testing_bodies` → `assemble` do `scaffold.java` (chyba = `INVALID_OUTPUT`).
2. `methods2test_execution.review`, rovnaký zoznam zakázaných API (chyba = `FORBIDDEN_API`).
3. `java_execution.evaluate_revision` raz, bez JaCoCo, proti `prepared["revision"]` (wrapper
   triedy + rovnaký classpath). Výsledok: `COMPILE_ERROR` (javac), `TEST_FAILURE`
   (assertion alebo iná výnimka), `NO_TESTS`, `PASSED`.
4. Skrytý referenčný test (`reference-private.java`) sa v slučke **nikdy nespúšťa ani nečíta**.

Konečné skóre posledného pokusu je potom presne existujúce `class_pass` (2 opakovania + JaCoCo,
`focal_invoked`). Ak slučka skončí na `PASSED`, ale 2 opakovania nie (flaky), počíta sa konečné skóre.

**Refactoring (MaRV, ML4Ref):**

1. `parse_answer(raw, file_path)` (chyba = `INVALID_OUTPUT`).
2. `refactoring_structural.valid_java` (chyba = `INVALID_JAVA` s pozíciou prvých 3 chybových uzlov).
3. Kontrola `no_op` (normalizovaný hash ako v `structural.evaluate`).
4. `refactoring_execution.detect` (RefactoringMiner 3.0.10 na páre vstup → výstup modelu).
5. **Verejný checker.** Rozhodne, či sa požadovaná operácia našla. Používa iba to, čo je v prompte:
   typ operácie, cieľové riadky vstupu a mená či typy z textu požiadavky (`request` je doslova
   RefactoringMiner opis gold udalosti, ktorý model už dostáva). Na kontrolu sa nepoužíva
   `target_event` ani `reference_path`. Pred behom treba overiť, že verejný checker dáva na všetkých
   800 uložených výstupoch rovnaký verdikt ako `structural_success` a že gold `after.java` prejde
   100/100 (časť 10, bod L5).

**Refactoring (SWE, 5 prípadov):** navyše kompilácia projektu s výstupom modelu. Do spätnej väzby
idú iba javac chyby v cieľovom súbore. Výsledky regresných testov projektu (`expected_tests`, Surefire
XML) **nejdú do spätnej väzby**, sú len konečným skóre.

---

## 5. Architektúra a napojenie na harness

### 5.1 Nové a zmenené súbory

| Súbor | Druh | Úloha |
|---|---|---|
| `configs/benchmarks/repair_loop_v1.json` | nový | protokol `repair_loop_cd_v1`, ramená, `source_runs`, `max_attempts: 3`, limity spätnej väzby, rovnaké dekódovacie parametre, `ontology_schema_version: project-ontology-v2`, hashe SHACL súborov |
| `scripts/benchmarks/run_repair_loop.py` | nový | CLI: `--task testing|refactoring --run-id X --source-run Y --cases pilot|all --arms ... [--dry-run|--freeze-only|--report-only]` |
| `src/llm_ontology/benchmarks/repair_loop.py` | nový | orchestrácia (`Loop` s `freeze`, `generate`, `evaluate`, `report`), ledger s rozpočtom `3 × bunky`, zápis pokusov |
| `src/llm_ontology/benchmarks/repair_feedback.py` | nový | normalizácia výstupov nástrojov na správy (mapovanie riadkov javac na telo, skrátenie, poradie) |
| `src/llm_ontology/ontology/project_facts.py` | nový | extrakcia faktov z projektu alebo classpath (časť 6) |
| `src/llm_ontology/ontology/output_facts.py` | nový | fakty z výstupu modelu: volania, argumenty, typy, nedeklarované mená, before/after deklarácie |
| `src/llm_ontology/ontology/shapes/{testing,refactoring}.ttl` | nový | presne súbory `shapes_*.ttl` z tohto návrhu (po pilote zmrazené hashom) |
| `src/llm_ontology/ontology/validate.py` | nový | `pyshacl.validate(..., advanced=True)`, prevod `sh:ValidationReport` na zoradené správy |
| `src/llm_ontology/ontology/graph.py` | rozšírený | TBox v2 ako nadmnožina v1 (časť 7). V1 bloky zmrazených behov sa nemenia, sú uložené v run adresároch. |
| `src/llm_ontology/ontology/views.py` | rozšírený | nové SPARQL pohľady `testing_view_v2`, `refactoring_view_v2` |
| `src/llm_ontology/ontology/guards.py` | rozšírený | `assert_grounded` aj pre fakty z projektu (allowlist zdrojov), kontrola n-gramov gold textu (časť 10) |
| `pyproject.toml` | zmena | extra `ontology = ["rdflib>=7,<8", "pyshacl>=0.30,<0.41"]` |
| `tests/test_repair_loop.py`, `tests/test_shapes.py` | nové | offline testy s mock providerom (`providers/` už má mock) a s dátami z `priklady/` |
| `AGENTS.md`, `docs/evaluation/README.md` | zmena | tretí runner a jeho pravidlá |

### 5.2 Čo sa použije bez zmeny

| Potreba | Existujúca funkcia |
|---|---|
| prompt pokusu 1 (testing) | `testing_matrix.Matrix.case` a `Matrix.prompt` pre rameno `qwen_base`, D cez `ontology.with_ontology` |
| prompt pokusu 1 (refactoring) | `refactoring_matrix.arm_instruction` a `render` (`block=` pre D) |
| volanie Ollama so schémou | `matrix_support._generate_direct`, `OllamaProvider.generate_result(prompt, json_schema=...)` |
| parsovanie a zostavenie | `inference.structured_output.parse_testing_bodies`, `matrix_support.assemble`, `refactoring_execution.parse_answer` |
| kontrola zdroja | `methods2test_execution.review` |
| kompilácia a beh | `java_execution.evaluate_revision`, `run_process` (timeouty, process groups) |
| RefactoringMiner | `refactoring_execution.detect`, `refactoring_structural.valid_java` |
| konečné skóre | `methods2test_metrics.evaluate`, `refactoring_structural.evaluate`, `refactoring_execution.evaluate` |
| identita modelu a adaptérov | `matrix_support.arm_hf_identity`, `freeze_hf_identities`, kontrola digestu Ollamy |
| zmrazenie bloku | `matrix_support.freeze_ontology`, `frozen_block` |

### 5.3 Rozloženie run adresára

```
artifacts/evaluation/runs/<run-id>/
  loop_plan.json                 # kópia configu + source_run + hashe selection/case/shapes
  selection.json                 # prevzaté zo source_run, overené hashom
  ontology/<project-key>/        # project.ttl, extraction.json (zdroje, hashe, vylúčené cesty)
  cases/<id>/
    case.json, scaffold.java, prepared.json      # prevzaté (testing), resp. cohort záznam (refactoring)
    ontology/ block.txt, case.ttl, identity.json # D blok v2, zmrazený pri --freeze-only
    loop/<arm>/attempt-<k>/
      prompt.txt  dispatch.json  received.json  raw.txt
      generated.java  check.json                 # výsledok nástroja počas slučky
      facts.ttl  shacl_report.ttl  shacl.json    # pri C iba tieňovo, do promptu nejde
      feedback.txt                               # presne text, ktorý dostal pokus k+1
      completion.json
    loop/<arm>/final/  metrics.json | evaluation/  # existujúci scorer na poslednom pokuse
  loop_summary.json  loop_report.md
```

Každý `prompt.txt` sa pred odoslaním porovná s tým, čo ledger skutočne odoslal (ako dnes). Pokus 1 sa
zmrazí pri `--freeze-only`. Pokusy 2–3 sa zmraziť nedajú, lebo závisia od výstupu, preto sa ukladá
ich hash a celý text.

---

## 6. Extrakcia projektových faktov

Cieľ: ontológia má obsahovať fakty, ktoré model **v prompte nevidí** alebo ich vidí len implicitne,
a nič, čo by prezradilo očakávaný výstup.

### 6.1 Testing (Methods2Test)

Dôležité obmedzenie harnessu: testovaná trieda je **wrapper**. `methods2test_harness.wrap_record`
z nej ponechá balík, importy, použité polia a focal metódu, ostatné členy a `extends` vynechá. Test sa
kompiluje proti `production-classes` tohto wrappera a JDK. Fakty z pôvodného GitHub projektu by preto
opisovali triedy a metódy, ktoré na classpath **nie sú**, a ťahali by model ku kompilačným chybám.
„Celý projekt“ je pri testingu to, proti čomu sa test naozaj kompiluje:

| Zdroj | Nástroj | Fakty |
|---|---|---|
| `production-classes` (bajtkód wrappera) | `javap -p -s -constants` | presné členy so signatúrami a viditeľnosťou, **implicitný konštruktor** (často jediný), `static`/`final`, deskriptory |
| zdrojový kód wrappera | tree-sitter (`ontology/extract.py`) | ktoré parametre focal metóda mení (`p.add`, `p.put`, `p.remove`, `p.clear`, `p.set`, `Collections.sort(p)` ...), nullable vetvy, vyhadzované výnimky |
| JDK (rovnaký `java_home` ako runtime) | `javap` na typy, na ktoré sa odkazuje focal metóda, polia a parametre, plus nadtypy do `java.lang.Object` | signatúry volaných JDK metód, hierarchia, kolekčné továrne a ich meniteľnosť (`List.of` nemeniteľná, `Arrays.asList` pevnej veľkosti, `new ArrayList` meniteľná) |
| scaffold | text | viditeľné typy (importy + `java.lang` + balík), statické importy asercií |

**Vylúčené:** `reference-private.java`, `raw-private.json` (obsahuje `test_case`), pôvodné repo
a **závislosti z `revision["dependencies"]`** (AssertJ alebo Hamcrest). Pridávajú sa na classpath
kvôli referenčnému testu, takže ich uvedenie v ontológii by prezradilo štýl gold testu.

### 6.2 Refactoring (MaRV, ML4Ref, SWE)

Tu celý projekt existuje: každý prípad má `commit` a `provenance`.

1. Získať strom **rodičovského commitu** (`git archive <commit>^`) z cache mirrorov
   (`refactoring_execution.acquire` už mirroruje SWE repá). Samotný commit, jeho správa ani neskoršia
   história sa nečítajú.
2. Overiť, že kontextová jednotka `before` je podmnožinou cieľového súboru v rodičovi (členy podľa
   `refactoring_context.Unit`). Pri nezhode alebo nedostupnom repe sa použije iba `before` a prípad sa
   označí `project_facts: unit_only`. Pokrytie sa reportuje.
3. Statická analýza všetkých `.java` súborov tree-sitterom (bez buildu, MaRV/ML4Ref sa nebuildujú).
   **Vylúčené** sú `**/src/test/**`, `**/test/**`, `**/*Test.java`, `**/*Tests.java`, `**/*IT.java` a
   testovacie zdroje.
4. Fakty: typy a hierarchia (`extends`/`implements` v rámci projektu), všetky členy cieľovej triedy
   vrátane tých, ktoré v kontextovej jednotke chýbajú, prepisované metódy (Rename Method a Remove
   Parameter musia zachovať override), volajúci cieľovej metódy (súbor a počet), polia s typmi a
   `final`, lokálne premenné cieľovej metódy s typmi a riadkami použitia.
5. Výsledok je jedna ABox na projekt a commit (`ontology/<project-key>/project.ttl`). Do bloku sa
   vyberie iba okolie cieľa (časť 7.3).

Pri refactoringu sa väčší prínos čaká od SHACL spätnej väzby než od faktov v bloku, lebo hodnotí sa
iba kontextová jednotka. Text práce to má povedať vopred.

### 6.3 Determinizmus a náklady

Extrakcia nevolá model. Výstup je zoradená N-Triples serializácia a jej SHA-256 ide do
`identity.json`, rovnako ako pri v1 (`graph_ntriples`). Meria sa čas extrakcie na projekt a veľkosť
grafu (počet trojíc), pretože zadanie chce aj nároky jednotlivých prístupov.

---

## 7. Schéma ontológie (TBox v2)

### 7.1 Triedy a vlastnosti

V2 je nadmnožina v1 (`graph.py`, namespace `https://w3id.org/llm-ontology/project#`). Doplnené pojmy
(OWL 2, Turtle):

```turtle
@prefix lo:   <https://w3id.org/llm-ontology/project#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# --- projekt a classpath ---
lo:ClassType a owl:Class ; rdfs:subClassOf lo:Type .
lo:InterfaceType a owl:Class ; rdfs:subClassOf lo:Type .
lo:EnumType a owl:Class ; rdfs:subClassOf lo:Type .
lo:RecordType a owl:Class ; rdfs:subClassOf lo:Type .
[] a owl:AllDisjointClasses ; owl:members ( lo:ClassType lo:InterfaceType lo:EnumType lo:RecordType ) .

lo:Executable a owl:Class ; rdfs:subClassOf lo:Member .
lo:Method rdfs:subClassOf lo:Executable .                  # lo:Method existuje už vo v1
lo:Constructor a owl:Class ; rdfs:subClassOf lo:Executable .
lo:Parameter a owl:Class ; rdfs:subClassOf lo:Variable .
lo:CollectionFactory a owl:Class ; rdfs:comment "JDK výraz, ktorý vytvára kolekciu, s jej meniteľnosťou." .
lo:Mutability a owl:Class ; owl:oneOf ( lo:Mutable lo:FixedSize lo:Immutable ) .

lo:directSuperType a owl:ObjectProperty ; rdfs:domain lo:Type ; rdfs:range lo:Type .
lo:extends a owl:ObjectProperty ; rdfs:subPropertyOf lo:directSuperType .
lo:implements a owl:ObjectProperty ; rdfs:subPropertyOf lo:directSuperType .
lo:overrides a owl:ObjectProperty ; rdfs:domain lo:Method ; rdfs:range lo:Method .
lo:calledFrom a owl:ObjectProperty ; rdfs:domain lo:Executable ; rdfs:range lo:Executable .
lo:mutatesParameter a owl:ObjectProperty ; rdfs:domain lo:Executable ; rdfs:range lo:Parameter .
lo:resultMutability a owl:ObjectProperty, owl:FunctionalProperty ;
    rdfs:domain lo:CollectionFactory ; rdfs:range lo:Mutability .

lo:fqn a owl:DatatypeProperty, owl:FunctionalProperty .
lo:simpleName a owl:DatatypeProperty .
lo:origin a owl:DatatypeProperty ; rdfs:comment "project | jdk | junit" .
lo:isFocal a owl:DatatypeProperty ; rdfs:range xsd:boolean .
lo:arity a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:range xsd:integer .
lo:isVarargs a owl:DatatypeProperty ; rdfs:range xsd:boolean .
lo:isImplicit a owl:DatatypeProperty ; rdfs:range xsd:boolean ; rdfs:comment "implicitný konštruktor" .
lo:visibility a owl:DatatypeProperty ; rdfs:comment "public | protected | package | private" .
lo:isStatic a owl:DatatypeProperty ; rdfs:range xsd:boolean .
lo:isFinal a owl:DatatypeProperty ; rdfs:range xsd:boolean .
lo:mutatedBy a owl:DatatypeProperty ; rdfs:comment "meno mutátora volaného na parametri" .
lo:factoryName a owl:DatatypeProperty .
lo:mutableAlternative a owl:DatatypeProperty .
lo:statementCount a owl:DatatypeProperty ; rdfs:range xsd:integer .

# --- fakty z výstupu modelu (ABox sa stavia pri každom pokuse) ---
lo:TestCall a owl:Class .          # volanie metódy alebo konštruktora v tele testu
lo:Argument a owl:Class .          # argument volania s pozíciou a pôvodom (napr. továreň)
lo:TypeUse a owl:Class .           # výskyt mena typu v tele
lo:UndeclaredName a owl:Class .    # identifikátor bez deklarácie v tele (lokálne, lambda, for, catch)
lo:Decl a owl:Class .              # deklarácia typu alebo člena na strane before/after
lo:Local a owl:Class ; rdfs:subClassOf lo:Variable .
lo:Use a owl:Class .               # použitie mena v metóde s rozlíšením local/parameter/field
lo:RefactoringRequest a owl:Class .
lo:ParameterizeVariableRequest rdfs:subClassOf lo:RefactoringRequest .
lo:ExtractMethodRequest rdfs:subClassOf lo:RefactoringRequest .
lo:InlineVariableRequest rdfs:subClassOf lo:RefactoringRequest .
lo:ExtractVariableRequest rdfs:subClassOf lo:RefactoringRequest .
lo:ReplaceVariableWithAttributeRequest rdfs:subClassOf lo:RefactoringRequest .

lo:receiverType a owl:ObjectProperty ; rdfs:domain lo:TestCall ; rdfs:range lo:Type .
lo:resolvesTo a owl:ObjectProperty .
lo:argumentOf a owl:ObjectProperty ; rdfs:domain lo:Argument ; rdfs:range lo:TestCall .
lo:producedBy a owl:ObjectProperty ; rdfs:domain lo:Argument ; rdfs:range lo:CollectionFactory .
lo:hasCounterpart a owl:ObjectProperty ; rdfs:domain lo:Decl ; rdfs:range lo:Decl .
lo:declaresLocal a owl:ObjectProperty ; rdfs:range lo:Local .
lo:hasUse a owl:ObjectProperty ; rdfs:range lo:Use .
lo:targetMethodBefore a owl:ObjectProperty ; rdfs:domain lo:RefactoringRequest .
lo:targetMethodAfter a owl:ObjectProperty ; rdfs:domain lo:RefactoringRequest .
lo:targetTypeAfter a owl:ObjectProperty ; rdfs:domain lo:RefactoringRequest .
# dátové: lo:calleeName lo:argCount lo:display lo:inBody lo:written lo:side lo:key lo:modifiers
#         lo:checkScope lo:oldName lo:newName lo:newType lo:expression lo:operationLabel
#         lo:invokes lo:resolvesKind lo:initializer
```

TBox má 31 tried (v1 mala 9). Úplná verzia bude v `graph.py` ako `SCHEMA_TTL`.

### 7.2 Prečo OWL aj SHACL

OWL 2 slúži na **opis** domény (triedy, hierarchia, funkčné vlastnosti, disjunktnosť) a platí
v ňom predpoklad otvoreného sveta: chýbajúci konštruktor neznamená, že neexistuje. Kontrola výstupu
modelu ale potrebuje **uzavretý svet**: „trieda má iba tieto konštruktory“. To je presne sémantika
SHACL, ktorý validuje dátový graf voči tvarom. Hierarchia sa rieši cestou `lo:directSuperType*`
priamo v SPARQL, takže netreba OWL reasoner a výsledok je deterministický. Toto rozdelenie
(OWL na schému, SHACL na integritné obmedzenia) zodpovedá odporúčanému použitiu W3C štandardov a
v práci ho treba výslovne zdôvodniť.

### 7.3 Blok do promptu (D, pokus 1)

Blok sa vyrenderuje SPARQL pohľadom ako v1, je deterministický, zoradený, má limit **400 tokenov**
a obal `<project-ontology>`. Vstupuje do promptu jediným miestom, `with_ontology`. Obsahuje iba fakty,
ktoré v prompte nie sú doslovne:

- *testing:* zoznam konštruktorov testovanej triedy (typicky iba `implicit public Foo()`), prístupné a
  neprístupné členy, ktoré parametre focal metóda mení a akým mutátorom, signatúry JDK metód volaných
  vo focal metóde, typy viditeľné v scaffolde a FQN ostatných potrebných JDK typov,
- *refactoring:* členy cieľovej triedy mimo kontextovej jednotky (iba signatúry), nadtypy a
  prepisované metódy, počet volajúcich cieľovej metódy v projekte, lokálne premenné cieľa s typmi a
  riadkami použitia, modifikátory deklarácií, ktoré sa nesmú zmeniť.

`guards.assert_grounded` sa rozšíri tak, že každé meno v bloku musí pochádzať zo vstupu, zo
scaffoldu, z JDK alebo z projektových faktov s povolenou cestou (časť 10).

---

## 8. SHACL obmedzenia

Úplné tvary sú v `shapes_testing.ttl` a `shapes_refactoring.ttl`. Používajú SHACL-SPARQL
(`sh:sparql`) a pySHACL s `advanced=True`. Na ručných dátach v `priklady/` dávajú presne
očakávané porušenia (testing 8, refactoring 13), zdedená metóda `toString()` a importovaný typ
neporušia nič.

### 8.1 Pravidlá a namerané chyby, z ktorých vychádzajú

Čísla sú z [najčastejších chýb](../2026-11-22_najcastejsie_chyby/README.md) a
[hĺbkovej analýzy](../2026-11-22_hlbkova_analyza_evalu/deep_analysis.md) (T1, R1, R2).

| ID | Tvar | Čo kontroluje | Nameraná chyba (single-shot, 100 prípadov) |
|---|---|---|---|
| T1 | `los:T1_CallMatchesSignature` | každé volanie metódy alebo konštruktora na známom type zodpovedá existujúcej a neprivátnej deklarácii (meno, arita, varargs, dedenie); správa vypíše deklarované signatúry | `wrong_arguments` 8 (ft), `access_violation`, `CFS:method` 6 (ft_v3_onto); „model viac odhaduje signatúry“ |
| T2 | `los:T2_NameIsDeclared` | žiadny nedeklarovaný identifikátor v tele; ak ide o pole testovanej triedy, správa povie jeho typ a viditeľnosť | `CFS:variable` 33–36 javac chýb pri FT ramenách, „neznáma premenná“ 6–8 buniek |
| T3 | `los:T3_MutatedParameterNeedsMutableArgument` | ak focal metóda mení parameter, argument nesmie byť z nemeniteľnej (`List.of`) alebo pevne veľkej (`Arrays.asList` pri `add`/`remove`) továrne | `runtime:unexpected_exception` (napr. `UnsupportedOperationException`) |
| T4 | `los:T4_TypeIsVisibleOnClasspath` | každý typ je importovaný, z `java.lang`, z balíka alebo plne kvalifikovaný a na classpath; importy sa pridať nedajú, správa navrhne FQN | `Lists`×5–6 (Guava, nie je na classpath), `ArrayList`×2–3, `Arrays`×6 (rag), `MyEnum` |
| R1 | `los:R1_ScopePreserved`, `los:R1_TargetMethodPresent` | mimo cieľa sa nestratí žiadny člen a nezmenia sa modifikátory; cieľová metóda vo výstupe existuje | „Change Class Access Modifier“ ×12 (base), ×28 pri Parameterize Variable |
| R2 | `los:R2_ParameterizeVariable` | lokálna premenná zmizne, metóda dostane parameter s menom a typom z požiadavky a použitia odkazujú naň | Parameterize Variable 1/10 (base), „iba Rename Variable“ ×21 |
| R3 | `los:R3_ExtractMethod` | nová metóda s menom z požiadavky je v tom istom type, zdrojová metóda ju volá a má menej príkazov | Extract Method 3/9 MaRV (base) |
| R4 | `los:R4_VariableLifecycle` | Inline Variable: deklarácia zmizne; Extract Variable: nová lokálna premenná s presným výrazom z požiadavky; Replace Variable With Attribute: lokálna premenná zmizne a pole sa používa | Inline 5/10, Extract Variable 4/10, Replace Variable With Attribute 5/10 (base) |

Rename, Rename Class a Remove Parameter vlastné pravidlo nemajú. Base ich zvláda v 63–100 % prípadov
a R1 ich čiastočne pokrýva.

### 8.2 Pravidlá a kompilátor

Väčšinu chýb T1, T2 a T4 nájde aj javac, takže C ich dostane tiež. Prínos D je v tom, že **ontológia
pridá opravnú informáciu, ktorú kompilátor nemá**, napríklad „deklarované: `Foo()`“, „je to privátne
pole typu int“ alebo „napíš `java.util.ArrayList`“. T3 a R1–R4 nájdu chyby, ktoré kompilátor nenájde
vôbec (výnimka až za behu, zlá alebo žiadna operácia v platnej Jave). Práve rozdiel medzi „čo je
zle“ (C) a „čo je zle a čo je správne podľa projektu“ (D) experiment meria.

### 8.3 Kalibrácia bez nových volaní modelu

Pred pilotom sa tvary spustia na všetkých uložených single-shot výstupoch (8 ramien × 100 prípadov ×
2 úlohy). Pre každé pravidlo sa vypočíta:

- **falošné poplachy:** podiel buniek, ktoré nástroj uznal (`class_pass` / `structural_success`),
  no pravidlo ich hlási. Cieľ ≤ 5 %. Pravidlo, ktoré to nesplní, sa sprísni alebo vypustí.
- **presnosť** P(neúspech | porušenie) ≥ 0,7 a **pokrytie** (koľko neúspechov aspoň jedno pravidlo
  hlási).

Tvary sa potom zmrazia (SHA-256 v `loop_plan.json`) a počas hlavného behu sa nemenia. Pravidlá sú
odvodené z kategórií chýb na tých istých 100 prípadoch. Je to hrozba pre validitu, ktorú treba
v práci priznať; zmierňuje ju to, že pravidlá sú všeobecné (nepoznajú konkrétne prípady) a že sa
reportuje aj analýza citlivosti na 80 prípadoch mimo pilota (časť 11).

---

## 9. Formát spätnej väzby

Spätná väzba je po anglicky (ako zvyšok promptu), deterministická, s pevným poradím a limitmi.
C a D majú rovnakú šablónu; C iba nemá sekciu `Ontology checks`.

```
### Previous answer (attempt {k} of 3)
{presne surová odpoveď modelu, pri testingu JSON s dvoma telami}

### Feedback on attempt {k}
Status: {INVALID_OUTPUT | FORBIDDEN_API | COMPILE_ERROR | TEST_FAILURE | NO_TESTS |
         INVALID_JAVA | NO_OP | OPERATION_MISSING}
Tool output ({javac | JUnit | parser | RefactoringMiner}), {n} of {N} messages:
- {správa 1}
- ...
Ontology checks (SHACL), {m} of {M} violations:          # iba D
- {sh:resultMessage 1}
- ...
Fix the reported problems. Keep everything else unchanged.
Return the complete answer in the same JSON format as before.
```

Pravidlá:

- **Limity:** najviac 5 správ nástroja a 5 porušení SHACL, každá najviac 300 znakov a spolu
  najviac 1 200 tokenov (Qwen tokenizer). Zvyšok sa skráti s označením `(+N more)`.
- **Poradie:** nástroj podľa riadku, SHACL podľa ID pravidla a riadku. Duplicitné správy sa zlúčia.
- **javac:** riadok v zostavenom súbore sa preloží na `test body 1|2, line n` (scaffold je pevný),
  text chyby ostane doslovný (`cannot find symbol`, `symbol: ...`, `location: ...`).
- **JUnit:** názov testu → telo, typ výnimky, prvý riadok správy (pri assertion aj `expected/but was`)
  a najvyšší rámec stacku v `GeneratedBodyTests`. Ide o výstup **vlastného testu modelu** proti
  vyhodnocovanej triede, nie o gold test.
- **RefactoringMiner:** `Requested: {request}` a potom až 5 operácií, ktoré RM našiel vo výstupe,
  napr. `Detected instead: Change Class Access Modifier public to package in class Calc`.
- **SWE build:** iba javac chyby cieľového súboru, nikdy výsledky regresných testov.
- **Tieňová validácia v C:** SHACL sa pustí aj na výstupy C a uloží sa do `shacl.json`, ale do
  promptu nejde. Tak sa porušenia dajú porovnať medzi ramenami.

Príklad (testing, D, po pokuse 1):

```
### Feedback on attempt 1
Status: COMPILE_ERROR
Tool output (javac), 2 of 2 messages:
- test body 1, line 1: constructor Foo in class Foo cannot be applied to given types; required: no arguments; found: int
- test body 2, line 3: cannot find symbol: variable count
Ontology checks (SHACL), 2 of 2 violations:
- T1 call new Foo(5) (test body 1, line 1) matches no accessible declaration with 1 argument(s). Declared: Foo()
- T2 name 'count' (test body 2, line 3) is not declared in this test body. It is a private field of Foo (type int); a test cannot use it as a local name.
Fix the reported problems. Keep everything else unchanged.
Return the complete answer in the same JSON format as before.
```

---

## 10. Kontrola data leaku

Do promptu ani do spätnej väzby nesmie ísť gold výstup ani skryté referenčné testy. Kontroly:

| # | Riziko | Opatrenie | Automatická kontrola |
|---|---|---|---|
| L1 | ontológia z gold testu | testing: zdrojmi sú iba wrapper, jeho bajtkód, JDK a scaffold; `reference-private.java`, `raw-private.json` a závislosti nie sú na allowliste | `extraction.json` zoznam čítaných súborov, test, že žiadna cesta neobsahuje `reference`, `raw-private`, `dependencies` |
| L2 | ontológia z gold refaktoringu | iba strom rodiča, bez commitu, histórie a testov; `record["output"]` a `reference_path` sa nečítajú | hash stromu rodiča, zoznam vylúčených ciest, test na zakázané kľúče záznamu |
| L3 | gold text v bloku alebo spätnej väzbe | `assert_grounded(..., forbidden=gold)` rozšírené: žiadny identifikátor ani 8-tokenový n-gram, ktorý je v gold texte a nie je vo verejnom vstupe (before, request, scaffold, prompt) | beží pri `--freeze-only` (blok) a po každom pokuse (spätná väzba) v samostatnom audit kroku, ktorý ako jediný smie čítať gold; nález zastaví beh |
| L4 | skryté testy v slučke | v slučke sa spúšťa iba test modelu; referenčný test a regresné testy SWE sú len v konečnom skóre | test na úrovni kódu: `repair_loop` neimportuje ani nevolá cesty k referenciám; ledger loguje každý spustený príkaz |
| L5 | stop kritérium refactoringu z gold udalosti | verejný checker z `request` a cieľových riadkov namiesto `target_event` | na uložených 800 výstupoch rovnaký verdikt ako `structural_success` (100 %), gold `after.java` prejde 100/100; inak sa beh nespustí |
| L6 | prompt a scorer sa rozídu | pokus 1 je zmrazený, každý ďalší prompt sa uloží celý a s hashom | `verify()` ako v maticiach |
| L7 | prekrytie s tréningovými dátami | rovnaké EVAL prípady ako vo finálnych behoch, už prešli overlap screenom | prevzaté z `selection.json`, hash |

Poznámka k testingu: správa `expected: <3> but was: <5>` model navedie na skutočnú hodnotu
z produkčného kódu. Nie je to leak gold výstupu (referenčný test sa nepoužije), ale robí to z úlohy
skôr generovanie regresných testov než odhad orákula. Platí to rovnako pre C aj D, takže porovnanie
ostáva férové. Meria sa to sekundárnou metrikou „prevzatá hodnota z feedbacku“ (časť 11).

---

## 11. Metriky a štatistika

### 11.1 Primárna metrika a testy

- **S@3:** konečný úspech po najviac 3 pokusoch, existujúcim scorerom na poslednom pokuse
  (testing `class_pass`, refactoring `structural_success`). Neúspech aj `unresolved` ostávajú
  v menovateli.
- **Primárne páry (2):** D vs C zvlášť pre testing a refactoring. Exaktný McNemar
  (`paired_tests.mcnemar_exact`), Holm cez 2 páry (`paired_tests.holm`), α = 0,05. Reportuje sa
  Both / A only / B only / Neither, Δ v p.b. a paired bootstrap 95 % CI (10 000, seed 42).

### 11.2 Sekundárne metriky (predregistrované, bez nároku na konfirmačný záver)

| Metrika | Definícia | Test alebo zobrazenie |
|---|---|---|
| S@1, S@2 | úspech po 1 a 2 pokusoch | McNemar D vs C; S@1 izoluje efekt bloku (H4) |
| krivka úspechu | S@k pre k = 1, 2, 3 a rameno | graf a tabuľka |
| volania na prípad | 1–3, neúspech = 3 | Wilcoxon signed-rank D vs C (`wilcoxon_signed_rank`), priemer a rozdelenie |
| pokusy do úspechu | neúspech = 4 (cenzúra) | citlivostná analýza, rovnaký test |
| porušenia pravidiel | bunky s ≥ 1 porušením po pravidlách a pokusoch (C tieňovo, D reálne) | tabuľka; McNemar „porušenie v poslednom pokuse“ D vs C (H3) |
| miera opravy porušenia | P(pravidlo r neporušené v k+1 \| porušené v k) | D vs C po pravidlách, ukazuje, či model správu SHACL využije |
| prechody statusov | napr. `COMPILE_ERROR → TEST_FAILURE → PASSED` | Sankey alebo matica prechodov |
| prevzatá hodnota (testing) | assertion v pokuse k+1 obsahuje literal z `but was` v pokuse k | podiel úspechov, ktoré tak vznikli, C aj D |
| line credit (testing) | existujúce pokrytie focal metódy | Wilcoxon, sekundárne |
| efekt slučky | C S@3 vs `qwen_base` single-shot, D vs `onto_project` | McNemar, rovnaký backend, mimo Holmovej rodiny (časť 11.3) |
| nároky | volania, vstupné a výstupné tokeny, čas generovania, čas nástrojov, čas SHACL, čas extrakcie, veľkosť grafu | priemer a medián na bunku, súčty na rameno |

### 11.3 Porovnanie s 8 doterajšími ramenami

Keďže C a D bežia na tých istých 100 prípadoch, výsledná tabuľka môže mať 10 riadkov na úlohu:
8 doterajších single-shot ramien a C, D. Každé rameno má rovnaký menovateľ a rovnaký scorer.

| Porovnanie | Typ | Čo ukazuje |
|---|---|---|
| D vs C | primárne, McNemar + Holm | prínos ontológie a SHACL v rovnakej slučke |
| C vs `qwen_base` | sekundárne, párové (rovnaký model, prompt aj backend) | čo pridá samotná slučka s nástrojom |
| D vs `onto_project` | sekundárne, párové | stará ontológia raz vs nová ontológia v slučke |
| C, D vs `skills`, `skills_onto`, `rag_single` | sekundárne, párové (rovnaký backend) | slučka oproti iným spôsobom dodania znalostí |
| C, D vs `ft_testing` / `ft_refactoring`, `ft_v3_onto`, `ft_onto` | iba opisné | iný backend (HF NF4), rovnako ako doterajšie porovnania s FT |

Pri sekundárnych porovnaniach treba v práci uviesť, že C a D majú až 3 volania modelu, kým
single-shot ramená iba jedno. Porovnanie je preto „za cenu viac volaní“ a uvádza sa spolu
s počtom volaní a časom.

### 11.4 Sila testu

Doterajšie primárne páry mali 9–17 % nesúhlasných párov a MDE ±9 až ±14 p.b. (80 % sila, α = 0,05).
Pri Holmovi cez 2 páry je najprísnejšia hladina 0,025, takže MDE vychádza okolo 11–15 p.b. Slučka
pravdepodobne zvýši podiel nesúhlasných párov. Pilot ho odhadne a MDE sa prepočíta pred hlavným
behom. Výsledok pod MDE sa formuluje ako „bez preukázateľného efektu“, nie ako „žiadny efekt“.

### 11.5 Citlivosť na pilot

Pilotných 20 prípadov sa môže podieľať na ladení formátu správ. Primárna analýza ide na 100
prípadoch, citlivostná na 80 prípadoch mimo pilota. Ak sa smer efektu líši, uvedie sa to.

---

## 12. Odhad volaní a času

### 12.1 Volania

Strop: 100 prípadov × 2 ramená (C, D) × 3 pokusy = 600 volaní na úlohu, teda **1 200 spolu**.
Očakávanie vychádza zo single-shot úspešnosti p₁ a predpokladu, že každá oprava vyrieši zhruba
štvrtinu zvyšných neúspechov. Volania na bunku = 1 + (1 − p₁) + (1 − p₂):

| Úloha | Rameno | p₁ (single-shot) | odhad volaní na bunku | volania (C + D) |
|---|---|---:|---:|---:|
| testing | base | 0,22 | 2,37 | 474 |
| refactoring | base | 0,60 | 1,70 | 340 |
| **spolu** | | | | **≈ 814** (strop 1 200) |

Pilot (20 prípadov na úlohu): ≈ 165 volaní, strop 240.

### 12.2 Čas

Uložené behy majú časy v `completion.json` (`generation_pipeline_seconds`, `seconds`), ale tie sú
iba v lokálnych artefaktoch, nie v gite. Nasledujúce čísla sú **predpoklady**, pilot ich nahradí
nameranými. Generovanie: Ollama ≈ 8 s (testing, ~300 výstupných tokenov) a ≈ 25 s (refactoring,
~1 000 tokenov). Nástroj v slučke: javac + JUnit ≈ 5 s, RefactoringMiner
≈ 8 s, SHACL ≈ 1 s. Konečné skóre testingu (2 × JaCoCo) ≈ 20 s na bunku.

| Úloha × rameno | volania | s na volanie (gen. + nástroj) | hodiny |
|---|---:|---:|---:|
| testing base | 474 | 14 | 1,8 |
| refactoring base | 340 | 34 | 3,2 |
| konečné skóre testingu | 200 buniek | 20 | 1,1 |
| extrakcia ontológie (≈ 100 repozitárov, git archive + tree-sitter) | | | 1–2 |
| **spolu** | | | **≈ 7–8 h** |

Beh sa dá rozdeliť po úlohách a ramenách a je
prerušiteľný rovnako ako matice (`dispatch.json` / `completion.json`).

---

## 13. Pilot na 20 prípadoch

**Výber (deterministický, pred behom):** v každej úlohe 20 zo 100 prípadov, stratifikovane podľa
výsledku `qwen_base` z finálneho behu (testing: pass / assertion / kompilácia / nevalidný výstup;
refactoring: 2 na každý typ operácie, z toho 1 SWE). V rámci vrstvy sa zoradí podľa
`sha256("pilot-v1" + id)` a vezme prvých k. Výsledok `qwen_base` nie je gold, ide len o rozloženie.

**Kontroly a kritériá „ide sa ďalej“:**

| # | Kontrola | Kritérium |
|---|---|---|
| P1 | determinizmus pokusu 1 | ≥ 95 % výstupov C pokusu 1 bajtovo zhodných s `qwen_base` finálneho behu; inak zdokumentovať a pokračovať s novými |
| P2 | verejný checker (L5) | 100 % zhoda na 800 uložených výstupoch a 100/100 gold |
| P3 | kalibrácia pravidiel (8.3) | každé pravidlo ≤ 5 % falošných poplachov |
| P4 | audit leaku (L1–L4) | 0 nálezov |
| P5 | dĺžka promptu | pokus 3 ≤ 8 000 tokenov a žiadne `output_truncated` |
| P6 | reakcia na opravný prompt | model vráti identickú odpoveď v ≤ 50 % opráv, inak upraviť šablónu spätnej väzby |
| P7 | infra | 0 `infrastructure_failure`, timeouty JVM a RefactoringMinera v limitoch |
| P8 | čas | nameraný čas na bunku → prepočet časti 12 |
| P9 | sila | odhad podielu nesúhlasných párov → prepočet MDE (11.3) |

Po pilote sa zmrazia `shapes/*.ttl`, šablóna spätnej väzby a limity (hashe v configu). Hlavný beh
dostane nové run ID a pilotné výsledky sa k nemu nepripočítavajú.

---

## 14. Riziká a obmedzenia

| Riziko | Dopad | Zmiernenie |
|---|---|---|
| D mení naraz blok aj spätnú väzbu | nedá sa úplne oddeliť, čo pomohlo | S@1 meria samotný blok; miera opravy porušení meria SHACL správy; prípadné ramená „iba blok“ a „iba SHACL“ sú rozšírenie, nie súčasť návrhu |
| pravidlá navrhnuté na tých istých prípadoch | nadhodnotený efekt | všeobecné pravidlá, kalibrácia iba na falošné poplachy, zmrazenie pred hlavným behom, citlivosť na 80 prípadoch |
| strop pri testingu: feedback s `but was` vyrieši veľa assertion chýb aj v C | malý rozdiel D vs C | predregistrované; reportuje sa metrika prevzatej hodnoty a S@1 |
| SHACL falošné poplachy (napr. nevyriešený typ prijímača, generiká, statické importy) | model „opravuje“ správny kód | tvary sa vyhodnocujú iba na rozlíšených faktoch (napr. `lo:receiverType` musí existovať), kalibrácia P3 |
| Ollama nie je bajtovo deterministická | pokus 1 sa líši od referencie | P1, reportovať; porovnanie D vs C ostáva párové v rámci nového behu |
| repo pre refactoring nedostupné | menej projektových faktov | fallback `unit_only`, reportované pokrytie |
| slučka spustí viac Java kódu modelu | bezpečnosť | ten istý `review` a `run_process` ako matice, nie je to OS sandbox (rovnaké priznanie) |
| dlhší čas behu | ≈ 7–8 h | prerušiteľnosť, pilot najprv |
| SWE n = 5 | žiadne závery | iba opisne, ako doteraz |

---

## 15. Ako to formulovať v práci

**Umiestnenie:** nová kapitola alebo podkapitola za vyhodnotením matíc, napríklad „Experiment 2:
ontológia ako zdroj overiteľných obmedzení v iteratívnej oprave“. Logika textu:

1. *Zistenie z experimentu 1:* ontológia zostavená z kódu, ktorý model vidí, je nadbytočná
   (`onto_project` vs `qwen_base`: 6/6 nesúhlasných párov v testingu, 5/10 v refactoringu).
2. *Hypotéza:* ontológia pomôže, ak (a) obsahuje fakty mimo kontextu (classpath, celý projekt) a
   (b) slúži na **kontrolu** výstupu, nie iba ako ďalší text v prompte.
3. *Dizajn:* dve ramená, ktoré sa líšia iba ontológiou. Slučka je rovnaká a nástroje, rozpočet,
   model, dekódovanie aj prípady tiež.
4. *Zdôvodnenie OWL + SHACL:* opis domény verzus integritné obmedzenia, otvorený a uzavretý svet
   (časť 7.2).
5. *Kontrola leaku a férovosti:* tabuľka L1–L7.

**Návrh vety do metodiky:** „Ramená C a D používajú rovnakú slučku s najviac troma pokusmi, v ktorej
model po každom neúspešnom pokuse dostane výstup kompilátora, testov alebo RefactoringMinera. Rameno D
navyše na začiatku dostane fakty z projektovej ontológie a po každom pokuse aj porušenia SHACL
obmedzení, ktoré sme odvodili z kategórií chýb nameraných v experimente 1. Ontológia sa buduje
z kódu, proti ktorému sa výstup kompiluje, resp. z rodičovského commitu projektu, a nikdy
nezahŕňa referenčné testy ani očakávaný výstup.“

**Formulácia výsledku:**

- významný rozdiel: „V tomto nastavení (Qwen2.5-Coder-7B, N = 100, ≤ 3 pokusy) zvýšilo rameno D
  konečnú úspešnosť o X p.b. (95 % CI …, p_Holm = …).“ Nehovoriť o ontológiách všeobecne.
- nevýznamný rozdiel: „Bez preukázateľného efektu pri N = 100; MDE ≈ Y p.b.“ Doplniť sekundárne
  metriky (volania, porušenia), ktoré môžu ukázať mechanizmus aj bez významnosti S@3.
- vždy oddeliť efekt bloku (S@1) a efekt SHACL spätnej väzby (miera opravy porušení).

**Súvisiaca literatúra (bibliografické údaje treba overiť):** slučky so spätnou väzbou z vykonávania
(Self-Debugging, Chen a kol. 2023; Reflexion, Shinn a kol. 2023), generovanie testov s opravou podľa
výsledkov behu (TestPilot, Schäfer a kol. 2023; ChatUniTest, Chen a kol.), štandardy W3C OWL 2 (2012)
a SHACL (2017), implementácia pySHACL.

**Obmedzenia do práce:** wrapper namiesto pôvodného projektu pri testingu, štrukturálne (nie
behaviorálne) hodnotenie refaktoringu mimo SWE, pravidlá navrhnuté na rovnakom súbore prípadov,
jeden model (bez FT), viac volaní modelu v C a D než v single-shot ramenách, D mení dve veci naraz.

---

## 16. Poradie implementácie

| Krok | Obsah | Model | Odhad práce |
|---|---|---|---|
| 1 | TBox v2, `project_facts.py` (javap, tree-sitter nad projektom), testy | nie | 3–4 dni |
| 2 | `output_facts.py`, `validate.py`, tvary z tohto návrhu, testy na `priklady/` | nie | 2–3 dni |
| 3 | verejný checker a kalibrácia pravidiel na uložených výstupoch (P2, P3) | nie | 1 deň |
| 4 | `repair_loop.py`, `repair_feedback.py`, runner, config, mock testy | nie (mock) | 3 dni |
| 5 | audit leaku (L1–L4) | nie | 1 deň |
| 6 | pilot 20 + 20 prípadov | áno, ≈ 165 volaní | ≈ 1,5–2 h behu |
| 7 | zmrazenie, hlavný beh | áno, ≈ 814 volaní | ≈ 7–8 h behu |
| 8 | report (`--report-only`), analýza, export do `thesis_materials/<dátum>_vysledky_slucky/` | nie | 1–2 dni |

Kroky 1–5 nepotrebujú GPU a dajú sa overiť testami v čistom klone. Kroky 3 a 5 sú zároveň pilotné
kontroly P2–P4.
