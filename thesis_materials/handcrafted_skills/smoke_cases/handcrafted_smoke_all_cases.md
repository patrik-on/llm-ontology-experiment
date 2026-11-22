# Všetky handcrafted smoke prípady na jednom mieste

> Archívny datasetový podklad. Jeho pôvodný smoke evaluátor bol odstránený; aktívne evaluácie sú výhradne Methods2Test matica a SWE refactoring matica.

Toto je prezentačný pohľad na **všetkých 24 ručne vytvorených smoke prípadov**: 12 pre generovanie testov a 12 pre refaktoring. Pri každom prípade je uvedený celý JSON záznam a celý obsah jeho fixture súborov. Nič nie je skrátené.

Zdrojom pravdy naďalej zostávajú:

- `data/smoke/testing/cases.jsonl`,
- `data/smoke/refactoring/cases.jsonl`,
- `data/smoke/**/fixtures/`.

Tento súbor je odvodený prezentačný dokument. Smoke dataset sa nepoužíva na fine-tuning ani RAG a nesmie sa indexovať.

## Ako čítať obsah

Testing prípady nemajú jednu ručne napísanú „správnu JUnit odpoveď“. Namiesto exact-match oracle definujú celý vstup, požadované scenáre, výnimky, minimálny počet testov a validačné pravidlá. To umožňuje uznať viac rôznych, ale správnych testovacích implementácií.

Refactoring prípady obsahujú ilustračný `reference_code` a samostatný `BehaviorTest.java`. Referenčný kód nie je exact-match oracle; rozhodujúca je kompilácia, behavior test, zachovanie API a štrukturálne očakávania.

## Čo z jedného záznamu dostáva model

Nie všetky riadky JSON záznamu sa posielajú modelu. Časť polí tvorí zadanie a zvyšok je skrytý evaluator-facing kontrakt, proveniencia alebo ochrana pred leakage. Toto oddelenie bráni tomu, aby prompt prezradil očakávané riešenie.

| Skupina údajov | Dostane model? | Ako ju používame |
|---|---:|---|
| `input.source_code` | áno | hlavný Java vstup v prompte |
| `input.requirements` | áno | explicitné požiadavky pripojené k zadaniu |
| `input.class_name`, `focal_method` | áno | z nich skladáme stručný project context |
| testing `package_name`, `test_framework`, `imports` | áno, ak sú vyplnené | ďalší project context pre generovanie kompilovateľného testu |
| `task` a `input.kind` | nepriamo | vyberú testing alebo refactoring prompt, výstupnú schému a metriku |
| `expected_process`, `expected_output`, `validation_rules` | **nie** | skrytý kontrakt pre validáciu, interpretáciu a hodnotenie |
| `reference_code`, `BehaviorTest.java` | **nie** | referencia a behavior oracle; model ich v zadaní nevidí |
| ID, náročnosť, názov, tagy, poznámky, cesty a hashe | nie | výber prípadov, reportovanie, kontrola konzistencie a leakage audit |

## Kompletný dátový slovník

### Spoločné top-level polia každého prípadu

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `id` | Stabilný unikátny identifikátor v tvare `<task>_<difficulty>_<NNN>`. | Výber konkrétneho prípadu, `case_id`, `run_id`, párovanie výsledkov a kontrola duplicít. |
| `task` | Hodnota `testing` alebo `refactoring`. | Prepína prompt, štruktúrovaný modelový výstup, retrieval filter a sadu metrík. Musí sa zhodovať s `input.kind` aj `expected_output.kind`. |
| `difficulty` | Ručne pridelená úroveň `easy`, `medium` alebo `tricky`. | Vyváženie datasetu, filtrovanie experimentov a report výsledkov podľa náročnosti; model ju v prompte nevidí. |
| `title` | Krátky ľudsky čitateľný názov prípadu. | Tabuľky, reporty a orientácia človeka; nie promptová požiadavka. |
| `input` | Vnorený objekt opisujúci modelový vstup a jeho fixtures. | Loader ho podľa `kind` validuje ako testing alebo refactoring vstup. |
| `expected_process` | Krátke kroky, ktoré opisujú rozumný spôsob vyriešenia prípadu. | Pomôcka pre človeka/evaluátora a audit pokrytia; nikdy sa neposiela modelu a nepovažuje sa za požadovaný chain-of-thought. |
| `expected_output` | Strojovo čitateľný kontrakt toho, čo má úspešný výstup spĺňať. | Kontrola schémy a konzistencie, tvorba referencie pri refactoringu a interpretácia výsledkov; je skrytý pred modelom. |
| `validation_rules` | Zoznam konkrétnych kontrol vo forme `{rule, value}`. | Deklaruje hodnotiaci checklist a umožňuje overiť, že prípad má povinné kritériá. Nejde o text promptu. |
| `tags` | Tematické značky, napr. `boundary`, `exception`, `extract-method`. | Kategorizácia, analýza pokrytia a ľudská navigácia; aktuálne nie sú súčasťou promptu. |
| `notes` | Doplňujúce interpretačné upozornenie alebo povolená alternatíva. | Dokumentácia pre evaluátora; model ju nevidí. |
| `input_code_hash` | SHA-256 presných UTF-8 bajtov `input.source_code`, citlivý aj na whitespace. | Odhalenie nechcenej zmeny dát a kontrola zhody uloženého záznamu. |
| `normalized_input_code_hash` | SHA-256 lexikálne normalizovaného Java vstupu: ignoruje komentáre a formátovací whitespace, ale zachováva tokeny a string literály. | Deduplikácia a leakage kontrola aj pri inom formátovaní rovnakého kódu. |
| `focal_method_hash` | Rovnaký normalizovaný hash, ale iba pre presne jednu metódu pomenovanú v `input.focal_method`. | Kontrola unikátnosti a odhalenie overlapu tej istej focal method v iných datasetoch. |

### Polia v `input` spoločné pre obe úlohy

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `kind` | Diskriminátor `testing`/`refactoring` pre vnorenú schému. | Pydantic podľa neho zvolí správny typ objektu; musí sedieť s `task`. |
| `class_name` | Názov Java triedy vo `source_code`. | Posiela sa v project context a používa sa v identite prípadu. |
| `source_code` | Celý Java zdroj, na ktorom má model pracovať. | Je to hlavný `input_text` promptu; musí sa kódovo zhodovať s obsahom `Input.java`. |
| `focal_method` | Primárna metóda, na ktorú je úloha zameraná. | Posiela sa v project context, testing metriky kontrolujú proxy jej volania a z metódy sa počíta `focal_method_hash`. |
| `requirements` | Ľudsky napísané požiadavky a hranice konkrétnej úlohy. | Pripájajú sa priamo do kanonického promptu vo všetkých režimoch, aby Direct, RAG a MultiRAG dostali rovnaké zadanie. |
| `fixture_path` | Cesta k samostatnému `Input.java`. | Dataset validator overí existenciu a obsahovú zhodu so `source_code` po orezaní okrajového whitespace; cesta sa modelu neposiela. |

### Dodatočné testing polia v `input`

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `test_framework` | Požadovaný framework; schéma povoľuje `JUnit 5`. | Uvádza sa v project context a očakávaný výstup ho musí rešpektovať. |
| `package_name` | Package testovanej triedy; prázdny reťazec znamená default package. | Ak je vyplnený, pridá sa do project contextu, aby model vytvoril správnu package deklaráciu. |
| `imports` | Importy, ktoré používa vstupný Java zdroj. | Ak zoznam nie je prázdny, zobrazí sa modelu ako declared imports a pomáha pri kompilovateľnosti testu. |

### Dodatočné refactoring pole v `input`

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `behavior_test_path` | Cesta k ručne napísanému JUnit `BehaviorTest.java`, ktorý kodifikuje pozorovateľné správanie. | Nie je v prompte. Offline validator ho spúšťa nad pôvodným vstupom aj nad `reference_code`, aby overil korektnosť smoke prípadu. |

### Testing polia v `expected_output`

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `kind` | Hodnota `testing`, diskriminátor výstupnej schémy. | Kontrola zhody s `task` a `input.kind`. |
| `must_compile` | Výstup musí byť kompilovateľný Java zdroj. | Povinný kontrakt; každý smoke prípad ho má `true`. |
| `must_use_framework` | Framework, ktorý má generovaný test používať. | Musí byť `JUnit 5` a zodpovedá `input.test_framework`. |
| `must_call_method` | Metóda, ktorú musí test reálne zavolať. | Musí sa zhodovať s `input.focal_method`; testing metriky počítajú regexový proxy indikátor jej volania. |
| `minimum_test_methods` | Minimálny požadovaný počet testovacích metód. | Per-case prah a súčasť validation kontraktu; metriky reportujú proxy počet testovacích metód. |
| `required_scenarios` | Konkrétne behaviorálne a hraničné scenáre, ktoré majú testy pokryť. | Checklist pre hodnotenie pokrytia; model ich nevidí, aby neunikla evaluator-facing referencia. |
| `expected_exception_types` | Presné Java exception typy, pre ktoré sa očakáva exception test. Prázdny zoznam znamená, že taká požiadavka nie je. | Musí byť v súlade s pravidlom `expected_exception_asserted`; metriky reportujú prítomnosť exception-test konštrukcie. |

### Refactoring polia v `expected_output`

| Pole | Čo znamená a prečo tam je | Ako ho používame |
|---|---|---|
| `kind` | Hodnota `refactoring`, diskriminátor výstupnej schémy. | Kontrola zhody s `task` a `input.kind`. |
| `expected_refactoring_types` | Jeden alebo viac očakávaných typov zmeny, napr. `Extract Method`. | Klasifikácia prípadu a interpretačný kontrakt; nevynucujeme exact textovú zhodu riešenia. |
| `must_compile` | Refaktorovaný výstup musí byť kompilovateľný. | Povinný kontrakt s hodnotou `true`. |
| `must_preserve_behavior` | Refaktoring nesmie zmeniť pozorovateľné správanie. | Zdôvodňuje behavior oracle a pravidlo `behavior_tests_pass`. |
| `must_preserve_public_api` | Verejné signatúry požadované zadaním sa nesmú zmeniť. | Kontrakt kontrolovaný cez príslušné pravidlo a behavior fixtures; model ho dostáva aj všeobecne v refactoring inštrukcii. |
| `structural_expectations` | Zoznam očakávaných štrukturálnych vlastností výsledku, napr. existencia helper metódy alebo odstránenie duplicity. | Užšie hodnotiace kritériá bez požiadavky na identický text. |
| `reference_code` | Jedna ručne napísaná ilustračná správna refaktorovaná verzia. | Experiment runner ju používa ako referenčný výstup pre podobnostné a code-health metriky; offline validator ju kompiluje a spúšťa s `BehaviorTest.java`. Model ju nevidí. |

### Polia objektu v `validation_rules`

| Pole | Čo znamená | Ako ho používame |
|---|---|---|
| `rule` | Strojový názov kontroly zo zoznamu povolených pravidiel. | Loader odmietne neznáme názvy a validator kontroluje povinné pravidlá pre danú úlohu. |
| `value` | Parameter pravidla: názov metódy, počet, exception typ, zoznam scenárov alebo štrukturálny cieľ. `null` znamená, že samotná prítomnosť pravidla vyjadruje boolean požiadavku. | Umožňuje porovnať konkrétnu požiadavku s `expected_output` a neskôr ju automatizovať. |

### Význam všetkých názvov `validation_rules.rule`

| Pravidlo | Čo požaduje | Stav použitia v aktuálnej pipeline |
|---|---|---|
| `code_compiles` | Java vstup/výstup sa má skompilovať. | Povinné v schéme; offline dataset validator kompiluje vstupy a referenčné riešenia. |
| `generated_tests_pass` | Vygenerované JUnit testy sa majú spustiť bez zlyhania nad testovanou triedou. | Povinný testing kontrakt; súčasný experiment runner zatiaľ reportuje hlavne textové/štrukturálne proxy metriky a toto pravidlo nad každou modelovou predikciou automaticky nespúšťa. |
| `invokes_focal_method` | Test musí volať metódu uvedenú vo `value`. | Hodnota sa validuje voči `must_call_method`; runner reportuje regexový `target_method_invocation_proxy`. |
| `minimum_test_methods` | Výstup má aspoň počet testovacích metód vo `value`. | Kontrakt sa zhoduje s `expected_output`; runner reportuje `test_method_count_proxy`, no per-case prah zatiaľ samostatne nevyhodnocuje. |
| `required_scenarios` | Testy majú pokryť kategórie uvedené vo `value`. | Evaluator-facing checklist; automatické semantické overenie všetkých scenárov zatiaľ nie je implementované. |
| `expected_exception_asserted` | Test má asertovať presný exception typ vo `value`. | Kontroluje sa konzistencia dát; runner reportuje všeobecný `has_exception_test`, nie vždy presný typ. |
| `public_api_preserved` | Refaktoring nesmie porušiť požadované verejné signatúry. | Povinný refactoring kontrakt; deklarované kritérium pre behavior/API validáciu. |
| `behavior_tests_pass` | Výsledok musí prejsť priloženým behavior testom. | Offline validator ho overuje na vstupe a `reference_code`; súčasný smoke experiment runner ho ešte nespúšťa nad každou modelovou predikciou. |
| `helper_method_exists` | Po Extract Method má existovať helper uvedený vo `value`. | Štrukturálny kontrakt/checklist; zatiaľ nie samostatná runtime metrika. |
| `focal_method_shorter` | Pôvodná focal method má byť po extrakcii kratšia. | Štrukturálny kontrakt; code metrics reportujú dĺžkové proxy, ale pravidlo sa nevyhodnocuje ako samostatné pass/fail. |
| `dead_code_removed` | Uvedený nepoužívaný kód alebo identifikátor má zmiznúť. | Štrukturálny checklist pre Remove Dead Code. |
| `boolean_expression_simplified` | Boolean logika má byť jednoduchšia pri zachovaní správania. | Štrukturálny checklist; všeobecné code-health metriky zachytia iba proxy zmenu. |
| `identifier_renamed` | Identifikátor má byť premenovaný alebo odstránený podľa `value`. | Úzke štrukturálne očakávanie, zatiaľ bez samostatného automatického pass/fail evaluátora. |
| `duplication_reduced` | Opakovaný fragment sa má zdieľať alebo extrahovať. | Štrukturálny checklist; súčasné metriky používajú iba všeobecné proxy. |

## Čo predstavujú priložené Java súbory

| Súbor | Účel | Dostane ho model? |
|---|---|---:|
| `Input.java` | Kanonická súborová kópia `input.source_code`; umožňuje reálnu kompiláciu mimo JSONL. | jeho obsah áno, cesta nie |
| `BehaviorTest.java` | Ručne napísaný JUnit oracle pre zachovanie správania refactoring prípadu. | nie |

## Dôležité obmedzenie aktuálnej automatizácie

Dáta už obsahujú bohatší hodnotiaci kontrakt, než dnes automaticky vykonáva experiment runner. Loader a offline validator kontrolujú schému, hashe, distribúciu, zhodu fixtures, kompiláciu vstupov a behavior testy pôvodného aj referenčného refactoring kódu. Bežný smoke experiment však pri modelových predikciách momentálne počíta hlavne generické testing/refactoring proxy metriky. `validation_rules` preto treba reportovať ako deklarovaný kontrakt; nie všetky jeho položky sú už automatický pass/fail test modelového výstupu.

## Ako aktuálne hodnotíme modelový výstup

Handcrafted smoke evaluácia má dve rozdielne vetvy. Testing vetva vyberie z modelovej odpovede `generated_tests`; refactoring vetva vyberie `refactored_code`. Nasledujúce diagramy zobrazujú **aktuálnu implementáciu**, nie iba plánovaný kontrakt.

### Testing: aktuálne hodnotenie `generated_tests`

```text
                  Generated test
                        │
       ┌────────────────┼─────────────────┐
       ▼                ▼                 ▼
  response validity   structure       heuristic quality
       │                │                 │
  valid JSON/schema    @Test present    trivial-test smell
  non-empty code       assertions       quality score 0–10
                       test count       coverage proxy label
                       focal call       low / medium / high
                       exception test
                       mocking proxy
```

Konkrétne testing metriky:

| Oblasť | Metrika | Čo reálne kontroluje |
|---|---|---|
| základ výstupu | `output_non_empty` | či model vrátil neprázdny Java text v poli `generated_tests` |
| veľkosť | `prediction_char_length`, `prediction_token_count` | dĺžka odpovede; sama osebe nehovorí o správnosti |
| testová štruktúra | `contains_test_annotation` | text obsahuje `@Test` |
| testová štruktúra | `test_method_count_proxy` | regexový odhad počtu testovacích metód |
| assertions | `assertion_count`, `has_assertion` | počet známych assertion volaní, napr. `assertEquals`, `assertThrows`, `assertThat` |
| zameranie | `target_method_invocation_proxy` | regexom zisťuje, či test pravdepodobne volá focal method |
| výnimky | `has_exception_test` | hľadá `assertThrows`, `catch`, `throws` alebo podobnú exception-test konštrukciu |
| mocking | `has_mocking` | hľadá Mockito/mock/when/verify konštrukcie; je to opisná metrika, nie automaticky plus alebo mínus |
| smell | `trivial_test_smell` | penalizuje prázdny test alebo triviálne assertions typu `assertTrue(true)` |
| agregácia | `generated_test_quality_score` | heuristický súčet vyššie uvedených signálov v rozsahu 0–10 |
| agregácia | `coverage_proxy_score/label` | rovnaký heuristický score prevedený na `invalid/low/medium/high`; **nejde o skutočné code coverage** |

`generated_test_quality_score` prideľuje +1 za neprázdny výstup, +2 za `@Test`, +2 za aspoň jednu assertion, +2 za proxy volania focal method, +1 za exception test a +1 za viac assertions alebo testovacích metód. Triviálny test odpočíta 3 body a prázdny výstup 5; výsledok sa oreže na 0–10. Coverage label je `high` od 7, `medium` od 4, `low` nad 0 a `invalid` pri 0.

Runner technicky uloží aj `exact_match`, `normalized_exact_match` a edit similarity. Testing prípady však zámerne nemajú `reference_output`, takže tieto reference-based hodnoty pri testing smoke nie sú zmysluplnou mierou kvality a nemajú sa reportovať ako úspešnosť.

### Čo testing vetva dnes ešte nerobí

```text
                  Generated test
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
     compilation      execution       test strength
        │               │                │
    compile@1        JUnit pass@1      line/branch coverage
                                        mutation score
                                        real bug detection

             NOT YET EXECUTED ON MODEL OUTPUT
```

To znamená, že dnešný `coverage_proxy` sa nesmie prezentovať ako JaCoCo line/branch coverage. Rovnako dnes pre modelový test nemáme reálne `compile@1`, `pass@1`, mutation score ani počet odhalených bugov. Tieto požiadavky sú čiastočne pripravené v `expected_output` a `validation_rules`, ale smoke runner ich zatiaľ všetky nevykonáva.

### Refactoring: aktuálne hodnotenie `refactored_code`

```text
                 Refactored code
                        │
       ┌────────────────┼──────────────────┐
       ▼                ▼                  ▼
  response validity   reference          code-health proxies
       │              comparison                 │
  valid JSON/schema   edit similarity      complexity delta
  non-empty code      exact-match info     nesting delta
  differs from input                       method-length delta
                                           cohesion proxy
                                           coupling proxy
                                           quality score 0–10
```

Konkrétne refactoring hodnotenie rieši:

| Oblasť | Čo meriame | Interpretácia |
|---|---|---|
| platnosť odpovede | neprázdny `refactored_code`, zmena oproti vstupu | model musí vrátiť kód a nesmie iba zopakovať vstup |
| referencia | normalized edit similarity k `reference_code` | podobnosť s jednou ručne napísanou variantou; iné behaviorálne ekvivalentné riešenie môže mať nižšie skóre |
| veľkosť a štruktúra | LOC, počet metód/tried/importov, priemerná a maximálna dĺžka metód, parametre a lokálne premenné | opis štrukturálnej zmeny pred/po |
| zložitosť | počty `if`, cyklov, `case`, `catch`, logických operátorov a `complexity_proxy_score` | heuristická zmena riadiacej zložitosti |
| vnorenie | `max_brace_nesting_depth` a jeho delta | či refaktoring sploštil alebo prehĺbil štruktúru |
| kvalita návrhu | `cohesion_proxy_score`, `coupling_proxy_score` | heuristické, nie statickým analyzátorom potvrdené cohesion/coupling |
| agregácia | `code_health_delta_score`, `refactoring_quality_score` | kombinované proxy skóre 0–10 |

`refactoring_quality_score` kombinuje: 1,5 bodu za zmenu oproti vstupu, až 2,5 bodu za podobnosť s referenciou, 25 % z `code_health_delta_score`, 20 % z cohesion proxy a bonus za nižší coupling proxy; výsledok sa oreže na 0–10. Vysoké skóre preto znamená dobrú kombináciu textovej podobnosti a heuristických code metrík, nie automaticky dokázanú behaviorálnu korektnosť.

### Čo refactoring vetva dnes ešte nerobí

```text
                 Refactored code
                        │
       ┌────────────────┼──────────────────┐
       ▼                ▼                  ▼
    compilation       behavior         exact constraints
       │                │                  │
    compile@1       BehaviorTest pass   public API diff
                                         helper exists
                                         rename/dead code
                                         duplication reduced

             NOT YET EXECUTED ON MODEL OUTPUT
```

Aktuálny runner teda nekompiluje každú modelovú refactoring predikciu a nespúšťa nad ňou príslušný `BehaviorTest.java`. Rovnako jednotlivé štrukturálne `validation_rules` ešte nemajú samostatný automatický pass/fail výsledok.

### Čo validujeme offline ešte pred experimentom

```text
              Handcrafted smoke case
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
     testing input              refactoring pair
          │                           │
    Input.java compiles       Input.java compiles
                              reference_code compiles
                              BehaviorTest passes before
                              BehaviorTest passes after
```

Toto offline overenie dokazuje, že ručne vytvorený benchmarkový prípad a jeho referencia sú konzistentné. **Nedokazuje však**, že rovnakými kontrolami prešiel modelový výstup; to je samostatná chýbajúca vrstva.

### Čo teda handcrafted smoke hodnotenie dnes rieši

- či funguje celý Direct/RAG/MultiRAG inference a reporting tok,
- či model vráti správnu štruktúrovanú odpoveď a neprázdny Java kód,
- či generovaný test vyzerá ako netriviálny JUnit test a volá focal method,
- či refaktoring niečo zmenil a ako sa zmenili proxy ukazovatele kódu,
- či je výstup podobný ručne napísanej refactoring referencii,
- porovnanie rovnakých prípadov medzi No-RAG, Single-RAG a MultiRAG režimom.

Na tvrdenie o funkčnej korektnosti testov alebo refaktoringu však treba doplniť kompiláciu modelového výstupu, reálne spustenie JUnit/BehaviorTest, coverage a pri test generation ideálne mutation testing alebo bug-detection benchmark.

## Obsah

| ID | Úloha | Náročnosť | Názov |
|---|---|---|---|
| `testing_easy_001` | `testing` | `easy` | Integer addition across signs |
| `testing_easy_002` | `testing` | `easy` | Even number predicate |
| `testing_easy_003` | `testing` | `easy` | Trimmed full-name formatting |
| `testing_easy_004` | `testing` | `easy` | Maximum of two integers |
| `testing_medium_001` | `testing` | `medium` | Integer division and zero denominator |
| `testing_medium_002` | `testing` | `medium` | Inclusive range validation |
| `testing_medium_003` | `testing` | `medium` | First matching product lookup |
| `testing_medium_004` | `testing` | `medium` | Whitespace and case normalization |
| `testing_tricky_001` | `testing` | `tricky` | Bounded mutable counter |
| `testing_tricky_002` | `testing` | `tricky` | Tiered shipping fee |
| `testing_tricky_003` | `testing` | `tricky` | Validated string window slicing |
| `testing_tricky_004` | `testing` | `tricky` | Score ledger state and immutable view |
| `refactoring_easy_001` | `refactoring` | `easy` | Inline one-use subtotal variable |
| `refactoring_easy_002` | `refactoring` | `easy` | Remove unused legacy label |
| `refactoring_easy_003` | `refactoring` | `easy` | Simplify access predicate |
| `refactoring_easy_004` | `refactoring` | `easy` | Rename ambiguous distance variable |
| `refactoring_medium_001` | `refactoring` | `medium` | Extract percentage discount calculation |
| `refactoring_medium_002` | `refactoring` | `medium` | Replace nested greeting checks with guards |
| `refactoring_medium_003` | `refactoring` | `medium` | Consolidate delivery handling day |
| `refactoring_medium_004` | `refactoring` | `medium` | Extract shared tax application |
| `refactoring_tricky_001` | `refactoring` | `tricky` | Extract unknown-device risk branch |
| `refactoring_tricky_002` | `refactoring` | `tricky` | Flatten booking eligibility checks |
| `refactoring_tricky_003` | `refactoring` | `tricky` | Decompose discount and regional tax |
| `refactoring_tricky_004` | `refactoring` | `tricky` | Extract notification priority policy |

# Testing: 12 prípadov

## 1. `testing_easy_001` — Integer addition across signs

- úloha: `testing`
- náročnosť: `easy`
- tagy: `arithmetic, pure-function, junit5`

### Celý JSONL záznam

```json
{
  "id": "testing_easy_001",
  "task": "testing",
  "difficulty": "easy",
  "title": "Integer addition across signs",
  "input": {
    "kind": "testing",
    "class_name": "Calculator",
    "source_code": "final class Calculator {\n    int add(int left, int right) {\n        return left + right;\n    }\n}",
    "focal_method": "add",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Cover positive, negative, and zero operands.",
    "fixture_path": "data/smoke/testing/fixtures/testing_easy_001/Input.java"
  },
  "expected_process": [
    "identify the add method contract",
    "cover representative operand signs",
    "generate deterministic JUnit 5 assertions"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "add",
    "minimum_test_methods": 3,
    "required_scenarios": [
      "positive values",
      "negative values",
      "zero operand"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "add"
    },
    {
      "rule": "minimum_test_methods",
      "value": 3
    },
    {
      "rule": "required_scenarios",
      "value": [
        "positive values",
        "negative values",
        "zero operand"
      ]
    }
  ],
  "tags": [
    "arithmetic",
    "pure-function",
    "junit5"
  ],
  "notes": "Integer overflow follows normal Java int semantics.",
  "input_code_hash": "3b8ae02ddbb747604737a5510bd3234c29c3ee8be3c47f468c95c9072be21d00",
  "normalized_input_code_hash": "9a9d11fb7d52aebe9cc88976a75614b1ff8d2b045c84de34d9edc0e4e3d23943",
  "focal_method_hash": "9a9d11fb7d52aebe9cc88976a75614b1ff8d2b045c84de34d9edc0e4e3d23943"
}
```

### Celý `data/smoke/testing/fixtures/testing_easy_001/Input.java`

```java
final class Calculator {
    int add(int left, int right) {
        return left + right;
    }
}
```

## 2. `testing_easy_002` — Even number predicate

- úloha: `testing`
- náročnosť: `easy`
- tagy: `boolean, modulo, boundary`

### Celý JSONL záznam

```json
{
  "id": "testing_easy_002",
  "task": "testing",
  "difficulty": "easy",
  "title": "Even number predicate",
  "input": {
    "kind": "testing",
    "class_name": "NumberParity",
    "source_code": "final class NumberParity {\n    boolean isEven(int value) {\n        return value % 2 == 0;\n    }\n}",
    "focal_method": "isEven",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Include positive, negative, and zero values.",
    "fixture_path": "data/smoke/testing/fixtures/testing_easy_002/Input.java"
  },
  "expected_process": [
    "identify parity semantics",
    "select even and odd representatives",
    "include zero and a negative input"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "isEven",
    "minimum_test_methods": 3,
    "required_scenarios": [
      "positive even and odd values",
      "negative value",
      "zero"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "isEven"
    },
    {
      "rule": "minimum_test_methods",
      "value": 3
    },
    {
      "rule": "required_scenarios",
      "value": [
        "positive parity",
        "negative parity",
        "zero"
      ]
    }
  ],
  "tags": [
    "boolean",
    "modulo",
    "boundary"
  ],
  "notes": "Negative even values are even in Java as well.",
  "input_code_hash": "09422e5319a035599459e7e3780efa44667e174966b852e97984ded7ec18b7a1",
  "normalized_input_code_hash": "9017bcf6b844b904dc47b7b6549669812581a53a26de2a5c6c5e9f5090a59129",
  "focal_method_hash": "9017bcf6b844b904dc47b7b6549669812581a53a26de2a5c6c5e9f5090a59129"
}
```

### Celý `data/smoke/testing/fixtures/testing_easy_002/Input.java`

```java
final class NumberParity {
    boolean isEven(int value) {
        return value % 2 == 0;
    }
}
```

## 3. `testing_easy_003` — Trimmed full-name formatting

- úloha: `testing`
- náročnosť: `easy`
- tagy: `strings, formatting, trim`

### Celý JSONL záznam

```json
{
  "id": "testing_easy_003",
  "task": "testing",
  "difficulty": "easy",
  "title": "Trimmed full-name formatting",
  "input": {
    "kind": "testing",
    "class_name": "NameFormatter",
    "source_code": "final class NameFormatter {\n    String fullName(String first, String last) {\n        return first.trim() + \" \" + last.trim();\n    }\n}",
    "focal_method": "fullName",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Verify normal names and surrounding whitespace.",
    "fixture_path": "data/smoke/testing/fixtures/testing_easy_003/Input.java"
  },
  "expected_process": [
    "identify trimming and separator behavior",
    "cover normal and padded names",
    "generate exact string assertions"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "fullName",
    "minimum_test_methods": 2,
    "required_scenarios": [
      "ordinary first and last name",
      "surrounding whitespace",
      "empty component"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "fullName"
    },
    {
      "rule": "minimum_test_methods",
      "value": 2
    },
    {
      "rule": "required_scenarios",
      "value": [
        "ordinary names",
        "whitespace trimming",
        "empty component"
      ]
    }
  ],
  "tags": [
    "strings",
    "formatting",
    "trim"
  ],
  "notes": "Null is outside the explicit contract and need not be tested.",
  "input_code_hash": "81d7e8e848b38ce62ce479322cf2b501b7dc5e1f91638f9166746adcd3929dd3",
  "normalized_input_code_hash": "ade7488f3fa2f2fc68bd0a88f17e470dcc500eab619e709313732aa014e69761",
  "focal_method_hash": "ade7488f3fa2f2fc68bd0a88f17e470dcc500eab619e709313732aa014e69761"
}
```

### Celý `data/smoke/testing/fixtures/testing_easy_003/Input.java`

```java
final class NameFormatter {
    String fullName(String first, String last) {
        return first.trim() + " " + last.trim();
    }
}
```

## 4. `testing_easy_004` — Maximum of two integers

- úloha: `testing`
- náročnosť: `easy`
- tagy: `comparison, branching, boundary`

### Celý JSONL záznam

```json
{
  "id": "testing_easy_004",
  "task": "testing",
  "difficulty": "easy",
  "title": "Maximum of two integers",
  "input": {
    "kind": "testing",
    "class_name": "IntSelector",
    "source_code": "final class IntSelector {\n    int max(int first, int second) {\n        return first >= second ? first : second;\n    }\n}",
    "focal_method": "max",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Cover both operand orders and equal inputs.",
    "fixture_path": "data/smoke/testing/fixtures/testing_easy_004/Input.java"
  },
  "expected_process": [
    "identify both ternary branches",
    "cover equal values",
    "generate direct equality assertions"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "max",
    "minimum_test_methods": 3,
    "required_scenarios": [
      "first is larger",
      "second is larger",
      "equal values"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "max"
    },
    {
      "rule": "minimum_test_methods",
      "value": 3
    },
    {
      "rule": "required_scenarios",
      "value": [
        "first branch",
        "second branch",
        "tie"
      ]
    }
  ],
  "tags": [
    "comparison",
    "branching",
    "boundary"
  ],
  "notes": "The observable result for equal inputs is their shared value.",
  "input_code_hash": "73df4958a5335d6450191e140ca2bb15f18627b8b7fd03f628f0a0ce1b0b0c70",
  "normalized_input_code_hash": "d2978120f4b582bfbdfdc0a9882b89d7436def2971a4a4e7c980e41c6e200b95",
  "focal_method_hash": "d2978120f4b582bfbdfdc0a9882b89d7436def2971a4a4e7c980e41c6e200b95"
}
```

### Celý `data/smoke/testing/fixtures/testing_easy_004/Input.java`

```java
final class IntSelector {
    int max(int first, int second) {
        return first >= second ? first : second;
    }
}
```

## 5. `testing_medium_001` — Integer division and zero denominator

- úloha: `testing`
- náročnosť: `medium`
- tagy: `arithmetic, exception, boundary`

### Celý JSONL záznam

```json
{
  "id": "testing_medium_001",
  "task": "testing",
  "difficulty": "medium",
  "title": "Integer division and zero denominator",
  "input": {
    "kind": "testing",
    "class_name": "Divider",
    "source_code": "final class Divider {\n    int divide(int numerator, int denominator) {\n        if (denominator == 0) {\n            throw new ArithmeticException(\"division by zero\");\n        }\n        return numerator / denominator;\n    }\n}",
    "focal_method": "divide",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Assert integer truncation, signs, and the exact exception type for zero.",
    "fixture_path": "data/smoke/testing/fixtures/testing_medium_001/Input.java"
  },
  "expected_process": [
    "identify success and exception branches",
    "cover Java integer truncation and signs",
    "assert ArithmeticException for zero"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "divide",
    "minimum_test_methods": 4,
    "required_scenarios": [
      "exact division",
      "truncated division",
      "negative result",
      "zero denominator"
    ],
    "expected_exception_types": [
      "ArithmeticException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "divide"
    },
    {
      "rule": "minimum_test_methods",
      "value": 4
    },
    {
      "rule": "expected_exception_asserted",
      "value": "ArithmeticException"
    },
    {
      "rule": "required_scenarios",
      "value": [
        "exact",
        "truncation",
        "sign",
        "zero denominator"
      ]
    }
  ],
  "tags": [
    "arithmetic",
    "exception",
    "boundary"
  ],
  "notes": "Tests must follow Java integer division rather than floating-point semantics.",
  "input_code_hash": "d0a0c8ee467f58d7806a4dd7ebf3448846115425c6680e119b50a0158e54f67d",
  "normalized_input_code_hash": "138e6a8e832a7d7046f07e0e1b82130e6a5ea90e1b2fc868144435db8c4cbbba",
  "focal_method_hash": "138e6a8e832a7d7046f07e0e1b82130e6a5ea90e1b2fc868144435db8c4cbbba"
}
```

### Celý `data/smoke/testing/fixtures/testing_medium_001/Input.java`

```java
final class Divider {
    int divide(int numerator, int denominator) {
        if (denominator == 0) {
            throw new ArithmeticException("division by zero");
        }
        return numerator / denominator;
    }
}
```

## 6. `testing_medium_002` — Inclusive range validation

- úloha: `testing`
- náročnosť: `medium`
- tagy: `range, boundary, exception`

### Celý JSONL záznam

```json
{
  "id": "testing_medium_002",
  "task": "testing",
  "difficulty": "medium",
  "title": "Inclusive range validation",
  "input": {
    "kind": "testing",
    "class_name": "RangeValidator",
    "source_code": "final class RangeValidator {\n    boolean isWithin(int value, int minimum, int maximum) {\n        if (minimum > maximum) {\n            throw new IllegalArgumentException(\"minimum exceeds maximum\");\n        }\n        return value >= minimum && value <= maximum;\n    }\n}",
    "focal_method": "isWithin",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Exercise both inclusive boundaries, outside values, and an invalid range.",
    "fixture_path": "data/smoke/testing/fixtures/testing_medium_002/Input.java"
  },
  "expected_process": [
    "identify inclusive boundary semantics",
    "cover values below and above the range",
    "assert invalid-range exception"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "isWithin",
    "minimum_test_methods": 5,
    "required_scenarios": [
      "minimum boundary",
      "maximum boundary",
      "inside value",
      "outside value",
      "invalid range"
    ],
    "expected_exception_types": [
      "IllegalArgumentException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "isWithin"
    },
    {
      "rule": "minimum_test_methods",
      "value": 5
    },
    {
      "rule": "expected_exception_asserted",
      "value": "IllegalArgumentException"
    },
    {
      "rule": "required_scenarios",
      "value": [
        "inclusive boundaries",
        "inside",
        "outside",
        "invalid range"
      ]
    }
  ],
  "tags": [
    "range",
    "boundary",
    "exception"
  ],
  "notes": "Minimum and maximum are both inclusive.",
  "input_code_hash": "ab56e03a940de77d1d4a0e401a462ebb839a6e95890526dc414088a4366f9815",
  "normalized_input_code_hash": "e10acbd78e7ea0f08f68475cf9f73b3b38f84430abfdb2d1bd62b03b1226e17e",
  "focal_method_hash": "e10acbd78e7ea0f08f68475cf9f73b3b38f84430abfdb2d1bd62b03b1226e17e"
}
```

### Celý `data/smoke/testing/fixtures/testing_medium_002/Input.java`

```java
final class RangeValidator {
    boolean isWithin(int value, int minimum, int maximum) {
        if (minimum > maximum) {
            throw new IllegalArgumentException("minimum exceeds maximum");
        }
        return value >= minimum && value <= maximum;
    }
}
```

## 7. `testing_medium_003` — First matching product lookup

- úloha: `testing`
- náročnosť: `medium`
- tagy: `collections, nullable, search`

### Celý JSONL záznam

```json
{
  "id": "testing_medium_003",
  "task": "testing",
  "difficulty": "medium",
  "title": "First matching product lookup",
  "input": {
    "kind": "testing",
    "class_name": "ProductCatalog",
    "source_code": "import java.util.List;\n\nfinal class ProductCatalog {\n    String findFirst(List<String> products, String query) {\n        if (products == null || query == null) {\n            return null;\n        }\n        for (String product : products) {\n            if (query.equals(product)) {\n                return product;\n            }\n        }\n        return null;\n    }\n}",
    "focal_method": "findFirst",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [
      "java.util.List"
    ],
    "requirements": "Cover a match, no match, empty collection, and supported null inputs.",
    "fixture_path": "data/smoke/testing/fixtures/testing_medium_003/Input.java"
  },
  "expected_process": [
    "identify first-match and null contracts",
    "cover present and absent values",
    "cover empty and null collections"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "findFirst",
    "minimum_test_methods": 4,
    "required_scenarios": [
      "matching element",
      "missing element",
      "empty list",
      "null input"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "findFirst"
    },
    {
      "rule": "minimum_test_methods",
      "value": 4
    },
    {
      "rule": "required_scenarios",
      "value": [
        "match",
        "no match",
        "empty list",
        "null"
      ]
    }
  ],
  "tags": [
    "collections",
    "nullable",
    "search"
  ],
  "notes": "The method deliberately returns null rather than Optional.",
  "input_code_hash": "30a7d8f92f4a09937d257c8d1d7bf843ade7fd40b4249460351f885fd7639390",
  "normalized_input_code_hash": "c6880a475d9ebce99658e3f3514449e15bdf5fa0543543f968b849146753d7ad",
  "focal_method_hash": "c6880a475d9ebce99658e3f3514449e15bdf5fa0543543f968b849146753d7ad"
}
```

### Celý `data/smoke/testing/fixtures/testing_medium_003/Input.java`

```java
import java.util.List;

final class ProductCatalog {
    String findFirst(List<String> products, String query) {
        if (products == null || query == null) {
            return null;
        }
        for (String product : products) {
            if (query.equals(product)) {
                return product;
            }
        }
        return null;
    }
}
```

## 8. `testing_medium_004` — Whitespace and case normalization

- úloha: `testing`
- náročnosť: `medium`
- tagy: `strings, nullable, normalization`

### Celý JSONL záznam

```json
{
  "id": "testing_medium_004",
  "task": "testing",
  "difficulty": "medium",
  "title": "Whitespace and case normalization",
  "input": {
    "kind": "testing",
    "class_name": "TextNormalizer",
    "source_code": "import java.util.Locale;\n\nfinal class TextNormalizer {\n    String normalize(String value) {\n        if (value == null || value.isBlank()) {\n            return \"\";\n        }\n        return value.trim().toLowerCase(Locale.ROOT).replaceAll(\"\\\\s+\", \" \").trim();\n    }\n}",
    "focal_method": "normalize",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [
      "java.util.Locale"
    ],
    "requirements": "Cover null, blank, mixed case, and repeated whitespace.",
    "fixture_path": "data/smoke/testing/fixtures/testing_medium_004/Input.java"
  },
  "expected_process": [
    "identify null and blank handling",
    "cover Locale.ROOT lowercasing",
    "verify whitespace collapse"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "normalize",
    "minimum_test_methods": 4,
    "required_scenarios": [
      "null input",
      "blank input",
      "mixed case",
      "repeated whitespace"
    ],
    "expected_exception_types": []
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "normalize"
    },
    {
      "rule": "minimum_test_methods",
      "value": 4
    },
    {
      "rule": "required_scenarios",
      "value": [
        "null",
        "blank",
        "case",
        "whitespace"
      ]
    }
  ],
  "tags": [
    "strings",
    "nullable",
    "normalization"
  ],
  "notes": "Locale.ROOT makes the case conversion deterministic.",
  "input_code_hash": "bf1452d49fa6d49b83447cd93a632081ee94d698d12a7702bd71dfdfc8cf7436",
  "normalized_input_code_hash": "0e6494ddc80ee2de8eed0017f5aff25eb907e722f26697ebe9fcb4db7b0fc59d",
  "focal_method_hash": "0e6494ddc80ee2de8eed0017f5aff25eb907e722f26697ebe9fcb4db7b0fc59d"
}
```

### Celý `data/smoke/testing/fixtures/testing_medium_004/Input.java`

```java
import java.util.Locale;

final class TextNormalizer {
    String normalize(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        return value.trim().toLowerCase(Locale.ROOT).replaceAll("\\s+", " ").trim();
    }
}
```

## 9. `testing_tricky_001` — Bounded mutable counter

- úloha: `testing`
- náročnosť: `tricky`
- tagy: `stateful, boundary, exception`

### Celý JSONL záznam

```json
{
  "id": "testing_tricky_001",
  "task": "testing",
  "difficulty": "tricky",
  "title": "Bounded mutable counter",
  "input": {
    "kind": "testing",
    "class_name": "BoundedCounter",
    "source_code": "final class BoundedCounter {\n    private int value;\n\n    BoundedCounter(int initial) {\n        if (initial < 0) {\n            throw new IllegalArgumentException(\"negative initial value\");\n        }\n        value = initial;\n    }\n\n    int increment(int limit) {\n        if (limit < 0) {\n            throw new IllegalArgumentException(\"negative limit\");\n        }\n        if (value < limit) {\n            value++;\n        }\n        return value;\n    }\n\n    int decrement() {\n        if (value > 0) {\n            value--;\n        }\n        return value;\n    }\n\n    int value() {\n        return value;\n    }\n}",
    "focal_method": "increment",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Verify state over repeated calls, upper and lower bounds, and invalid arguments.",
    "fixture_path": "data/smoke/testing/fixtures/testing_tricky_001/Input.java"
  },
  "expected_process": [
    "identify mutable state and bounds",
    "exercise repeated increments and decrements",
    "assert invalid constructor or limit arguments"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "increment",
    "minimum_test_methods": 5,
    "required_scenarios": [
      "state changes across calls",
      "increment stops at limit",
      "decrement stops at zero",
      "negative initial value",
      "negative limit"
    ],
    "expected_exception_types": [
      "IllegalArgumentException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "increment"
    },
    {
      "rule": "minimum_test_methods",
      "value": 5
    },
    {
      "rule": "expected_exception_asserted",
      "value": "IllegalArgumentException"
    },
    {
      "rule": "required_scenarios",
      "value": [
        "state",
        "upper bound",
        "lower bound",
        "invalid inputs"
      ]
    }
  ],
  "tags": [
    "stateful",
    "boundary",
    "exception"
  ],
  "notes": "Each test should create its own counter to avoid order dependence.",
  "input_code_hash": "08eaa45735e5b176d3c378de5f9b66b554ea63b349d0f1acb53d248dab99442e",
  "normalized_input_code_hash": "bb4108ab2c77a1fa9e3c64780514f77f1798a6f4a1dd77458b76697477e11302",
  "focal_method_hash": "60efda54821ee8ffc4cf36a67393eb9f5619c17b092d3021fe065d45cfdb694b"
}
```

### Celý `data/smoke/testing/fixtures/testing_tricky_001/Input.java`

```java
final class BoundedCounter {
    private int value;

    BoundedCounter(int initial) {
        if (initial < 0) {
            throw new IllegalArgumentException("negative initial value");
        }
        value = initial;
    }

    int increment(int limit) {
        if (limit < 0) {
            throw new IllegalArgumentException("negative limit");
        }
        if (value < limit) {
            value++;
        }
        return value;
    }

    int decrement() {
        if (value > 0) {
            value--;
        }
        return value;
    }

    int value() {
        return value;
    }
}
```

## 10. `testing_tricky_002` — Tiered shipping fee

- úloha: `testing`
- náročnosť: `tricky`
- tagy: `branching, threshold, exception`

### Celý JSONL záznam

```json
{
  "id": "testing_tricky_002",
  "task": "testing",
  "difficulty": "tricky",
  "title": "Tiered shipping fee",
  "input": {
    "kind": "testing",
    "class_name": "ShippingFee",
    "source_code": "final class ShippingFee {\n    int calculate(int orderCents, boolean express, boolean member) {\n        if (orderCents < 0) {\n            throw new IllegalArgumentException(\"negative order total\");\n        }\n        if (orderCents >= 5000) {\n            return 0;\n        }\n        int fee = express ? 1200 : 500;\n        if (member) {\n            fee -= 200;\n        }\n        return Math.max(fee, 0);\n    }\n}",
    "focal_method": "calculate",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Cover free shipping, regular/express fees, membership discount, and invalid totals.",
    "fixture_path": "data/smoke/testing/fixtures/testing_tricky_002/Input.java"
  },
  "expected_process": [
    "map all independent decision branches",
    "cover the exact free-shipping threshold",
    "assert invalid total handling"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "calculate",
    "minimum_test_methods": 6,
    "required_scenarios": [
      "regular non-member",
      "regular member",
      "express non-member",
      "express member",
      "free-shipping threshold",
      "negative total"
    ],
    "expected_exception_types": [
      "IllegalArgumentException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "calculate"
    },
    {
      "rule": "minimum_test_methods",
      "value": 6
    },
    {
      "rule": "expected_exception_asserted",
      "value": "IllegalArgumentException"
    },
    {
      "rule": "required_scenarios",
      "value": [
        "fee branches",
        "membership",
        "threshold",
        "invalid total"
      ]
    }
  ],
  "tags": [
    "branching",
    "threshold",
    "exception"
  ],
  "notes": "Amounts are integer cents, avoiding floating-point ambiguity.",
  "input_code_hash": "47820570bca7d0867aff132cf17c5eb976279e414f61292615ef62d69ec1de92",
  "normalized_input_code_hash": "5ad3fed7d176c0e9910e8f60ce03d220a596b507ac059db88418c563c8d9f6ff",
  "focal_method_hash": "5ad3fed7d176c0e9910e8f60ce03d220a596b507ac059db88418c563c8d9f6ff"
}
```

### Celý `data/smoke/testing/fixtures/testing_tricky_002/Input.java`

```java
final class ShippingFee {
    int calculate(int orderCents, boolean express, boolean member) {
        if (orderCents < 0) {
            throw new IllegalArgumentException("negative order total");
        }
        if (orderCents >= 5000) {
            return 0;
        }
        int fee = express ? 1200 : 500;
        if (member) {
            fee -= 200;
        }
        return Math.max(fee, 0);
    }
}
```

## 11. `testing_tricky_003` — Validated string window slicing

- úloha: `testing`
- náročnosť: `tricky`
- tagy: `indexes, strings, exceptions`

### Celý JSONL záznam

```json
{
  "id": "testing_tricky_003",
  "task": "testing",
  "difficulty": "tricky",
  "title": "Validated string window slicing",
  "input": {
    "kind": "testing",
    "class_name": "WindowSlice",
    "source_code": "final class WindowSlice {\n    String slice(String value, int start, int length) {\n        if (value == null) {\n            throw new IllegalArgumentException(\"value is null\");\n        }\n        if (start < 0 || length < 0 || start > value.length() - length) {\n            throw new IndexOutOfBoundsException(\"invalid window\");\n        }\n        return value.substring(start, start + length);\n    }\n}",
    "focal_method": "slice",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [],
    "requirements": "Cover zero length, end boundary, and each invalid-input family.",
    "fixture_path": "data/smoke/testing/fixtures/testing_tricky_003/Input.java"
  },
  "expected_process": [
    "identify the valid index relation",
    "cover zero-length and end-aligned windows",
    "assert null and index exception types"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "slice",
    "minimum_test_methods": 6,
    "required_scenarios": [
      "middle slice",
      "end boundary",
      "zero length",
      "negative start or length",
      "window beyond end",
      "null value"
    ],
    "expected_exception_types": [
      "IllegalArgumentException",
      "IndexOutOfBoundsException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "slice"
    },
    {
      "rule": "minimum_test_methods",
      "value": 6
    },
    {
      "rule": "expected_exception_asserted",
      "value": [
        "IllegalArgumentException",
        "IndexOutOfBoundsException"
      ]
    },
    {
      "rule": "required_scenarios",
      "value": [
        "valid window",
        "boundaries",
        "negative index",
        "overflow window",
        "null"
      ]
    }
  ],
  "tags": [
    "indexes",
    "strings",
    "exceptions"
  ],
  "notes": "The subtraction-based bounds check avoids start+length integer overflow.",
  "input_code_hash": "afd2145208fdf5a5b53fbb47450fb67fea9d3fed567517e61614a40ba8a0ffd4",
  "normalized_input_code_hash": "2d95e22d6d9c126ec683763e2366c490059ba474c259d77fc03eff2a46d094d6",
  "focal_method_hash": "2d95e22d6d9c126ec683763e2366c490059ba474c259d77fc03eff2a46d094d6"
}
```

### Celý `data/smoke/testing/fixtures/testing_tricky_003/Input.java`

```java
final class WindowSlice {
    String slice(String value, int start, int length) {
        if (value == null) {
            throw new IllegalArgumentException("value is null");
        }
        if (start < 0 || length < 0 || start > value.length() - length) {
            throw new IndexOutOfBoundsException("invalid window");
        }
        return value.substring(start, start + length);
    }
}
```

## 12. `testing_tricky_004` — Score ledger state and immutable view

- úloha: `testing`
- náročnosť: `tricky`
- tagy: `stateful, collections, immutability`

### Celý JSONL záznam

```json
{
  "id": "testing_tricky_004",
  "task": "testing",
  "difficulty": "tricky",
  "title": "Score ledger state and immutable view",
  "input": {
    "kind": "testing",
    "class_name": "ScoreLedger",
    "source_code": "import java.util.ArrayList;\nimport java.util.List;\n\nfinal class ScoreLedger {\n    private final List<Integer> scores = new ArrayList<>();\n\n    void addScore(int score) {\n        if (score < 0 || score > 100) {\n            throw new IllegalArgumentException(\"score outside 0..100\");\n        }\n        scores.add(score);\n    }\n\n    List<Integer> scores() {\n        return List.copyOf(scores);\n    }\n\n    double average() {\n        return scores.stream().mapToInt(Integer::intValue).average().orElse(0.0);\n    }\n}",
    "focal_method": "addScore",
    "test_framework": "JUnit 5",
    "package_name": "",
    "imports": [
      "java.util.ArrayList",
      "java.util.List"
    ],
    "requirements": "Verify state, average, input bounds, and immutability of the returned list.",
    "fixture_path": "data/smoke/testing/fixtures/testing_tricky_004/Input.java"
  },
  "expected_process": [
    "identify score bounds and mutable internal state",
    "verify derived average after multiple calls",
    "verify returned list cannot mutate the ledger"
  ],
  "expected_output": {
    "kind": "testing",
    "must_compile": true,
    "must_use_framework": "JUnit 5",
    "must_call_method": "addScore",
    "minimum_test_methods": 5,
    "required_scenarios": [
      "empty average",
      "multiple scores and average",
      "boundary scores 0 and 100",
      "out-of-range score",
      "immutable returned list"
    ],
    "expected_exception_types": [
      "IllegalArgumentException",
      "UnsupportedOperationException"
    ]
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "generated_tests_pass",
      "value": null
    },
    {
      "rule": "invokes_focal_method",
      "value": "addScore"
    },
    {
      "rule": "minimum_test_methods",
      "value": 5
    },
    {
      "rule": "expected_exception_asserted",
      "value": [
        "IllegalArgumentException",
        "UnsupportedOperationException"
      ]
    },
    {
      "rule": "required_scenarios",
      "value": [
        "empty state",
        "state accumulation",
        "score boundaries",
        "immutable view"
      ]
    }
  ],
  "tags": [
    "stateful",
    "collections",
    "immutability"
  ],
  "notes": "The list returned by scores is an immutable snapshot.",
  "input_code_hash": "c305759565a36cf2bf1797ecbaf61d9c776097af2c18e5e178cd2c7e352acddb",
  "normalized_input_code_hash": "0ab4461239f28bafca0197dc73125f26c43bfe3812f25f194f08ce65a506e2ff",
  "focal_method_hash": "4602e8e9b30c568685c5f39f573fc8dc0e71f37a1598b0f6362e8b0910fef3b3"
}
```

### Celý `data/smoke/testing/fixtures/testing_tricky_004/Input.java`

```java
import java.util.ArrayList;
import java.util.List;

final class ScoreLedger {
    private final List<Integer> scores = new ArrayList<>();

    void addScore(int score) {
        if (score < 0 || score > 100) {
            throw new IllegalArgumentException("score outside 0..100");
        }
        scores.add(score);
    }

    List<Integer> scores() {
        return List.copyOf(scores);
    }

    double average() {
        return scores.stream().mapToInt(Integer::intValue).average().orElse(0.0);
    }
}
```


# Refactoring: 12 prípadov

## 1. `refactoring_easy_001` — Inline one-use subtotal variable

- úloha: `refactoring`
- náročnosť: `easy`
- tagy: `inline-variable, readability, arithmetic`

### Celý JSONL záznam

```json
{
  "id": "refactoring_easy_001",
  "task": "refactoring",
  "difficulty": "easy",
  "title": "Inline one-use subtotal variable",
  "input": {
    "kind": "refactoring",
    "class_name": "InvoiceTotal",
    "source_code": "final class InvoiceTotal {\n    int total(int unitPrice, int quantity) {\n        int subtotal = unitPrice * quantity;\n        return subtotal;\n    }\n}",
    "focal_method": "total",
    "requirements": "Inline the temporary subtotal variable without changing the public method signature.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_easy_001/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_easy_001/BehaviorTest.java"
  },
  "expected_process": [
    "identify the one-use local variable",
    "inline its expression at the return",
    "preserve method behavior and signature"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Inline Variable"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "local variable subtotal is removed"
    ],
    "reference_code": "final class InvoiceTotal {\n    int total(int unitPrice, int quantity) {\n        return unitPrice * quantity;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "identifier_renamed",
      "value": "subtotal removed"
    }
  ],
  "tags": [
    "inline-variable",
    "readability",
    "arithmetic"
  ],
  "notes": "Reference code is illustrative; equivalent direct-return implementations are valid.",
  "input_code_hash": "26ed3877a89390679311d8816c555a2eaf066166276b6c5d89e30761148f6c82",
  "normalized_input_code_hash": "853d3c070fdd4a25f4e987a170a58798e263db2a5a86faa05983ae71b940cd5a",
  "focal_method_hash": "853d3c070fdd4a25f4e987a170a58798e263db2a5a86faa05983ae71b940cd5a"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_001/Input.java`

```java
final class InvoiceTotal {
    int total(int unitPrice, int quantity) {
        int subtotal = unitPrice * quantity;
        return subtotal;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_001/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final InvoiceTotal subject = new InvoiceTotal();

    @Test
    void preservesArithmeticAcrossRepresentativeValues() {
        assertEquals(30, subject.total(10, 3));
        assertEquals(0, subject.total(99, 0));
        assertEquals(-14, subject.total(-7, 2));
    }
}
```

## 2. `refactoring_easy_002` — Remove unused legacy label

- úloha: `refactoring`
- náročnosť: `easy`
- tagy: `dead-code, branching, readability`

### Celý JSONL záznam

```json
{
  "id": "refactoring_easy_002",
  "task": "refactoring",
  "difficulty": "easy",
  "title": "Remove unused legacy label",
  "input": {
    "kind": "refactoring",
    "class_name": "StatusLabel",
    "source_code": "final class StatusLabel {\n    String label(boolean active) {\n        String unused = \"legacy\";\n        if (active) {\n            return \"ACTIVE\";\n        }\n        return \"INACTIVE\";\n    }\n}",
    "focal_method": "label",
    "requirements": "Remove dead local code while preserving both return branches.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_easy_002/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_easy_002/BehaviorTest.java"
  },
  "expected_process": [
    "identify the unused local assignment",
    "remove only dead code",
    "verify both observable branches"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Remove Dead Code"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "unused local variable is absent"
    ],
    "reference_code": "final class StatusLabel {\n    String label(boolean active) {\n        if (active) {\n            return \"ACTIVE\";\n        }\n        return \"INACTIVE\";\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "dead_code_removed",
      "value": "unused"
    }
  ],
  "tags": [
    "dead-code",
    "branching",
    "readability"
  ],
  "notes": "No return value or branch may change.",
  "input_code_hash": "d17c6e8ab86ea1d6690c213e70665b923efb5928c6942e63b77df17f1c4d495c",
  "normalized_input_code_hash": "603b6375d4f4c196f40ddec1ea657a39bc3bd7ef79c67cc89390858d2512667d",
  "focal_method_hash": "603b6375d4f4c196f40ddec1ea657a39bc3bd7ef79c67cc89390858d2512667d"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_002/Input.java`

```java
final class StatusLabel {
    String label(boolean active) {
        String unused = "legacy";
        if (active) {
            return "ACTIVE";
        }
        return "INACTIVE";
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_002/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesBothStatusBranches() {
        StatusLabel subject = new StatusLabel();
        assertEquals("ACTIVE", subject.label(true));
        assertEquals("INACTIVE", subject.label(false));
    }
}
```

## 3. `refactoring_easy_003` — Simplify access predicate

- úloha: `refactoring`
- náročnosť: `easy`
- tagy: `boolean, truth-table, readability`

### Celý JSONL záznam

```json
{
  "id": "refactoring_easy_003",
  "task": "refactoring",
  "difficulty": "easy",
  "title": "Simplify access predicate",
  "input": {
    "kind": "refactoring",
    "class_name": "AccessPolicy",
    "source_code": "final class AccessPolicy {\n    boolean canAccess(boolean enabled, boolean locked) {\n        if (enabled == true && locked == false) {\n            return true;\n        } else {\n            return false;\n        }\n    }\n}",
    "focal_method": "canAccess",
    "requirements": "Replace redundant boolean comparisons and branches with an equivalent expression.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_easy_003/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_easy_003/BehaviorTest.java"
  },
  "expected_process": [
    "derive the equivalent boolean predicate",
    "remove redundant true/false branches",
    "preserve the complete truth table"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Simplify Boolean Expression"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "no comparison to boolean literals",
      "direct boolean return"
    ],
    "reference_code": "final class AccessPolicy {\n    boolean canAccess(boolean enabled, boolean locked) {\n        return enabled && !locked;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "boolean_expression_simplified",
      "value": true
    }
  ],
  "tags": [
    "boolean",
    "truth-table",
    "readability"
  ],
  "notes": "All four input combinations are covered by the behavior test.",
  "input_code_hash": "ca57501eece3665205ca985c2dd657ef9290d3cabce367ef772bedab477e4082",
  "normalized_input_code_hash": "3fe3681b97b8bc4ee7f93efe841ed34fa73fbad466d1b0f8ad07e37120476f9e",
  "focal_method_hash": "3fe3681b97b8bc4ee7f93efe841ed34fa73fbad466d1b0f8ad07e37120476f9e"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_003/Input.java`

```java
final class AccessPolicy {
    boolean canAccess(boolean enabled, boolean locked) {
        if (enabled == true && locked == false) {
            return true;
        } else {
            return false;
        }
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_003/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesCompleteTruthTable() {
        AccessPolicy subject = new AccessPolicy();
        assertEquals(false, subject.canAccess(false, false));
        assertEquals(false, subject.canAccess(false, true));
        assertEquals(true, subject.canAccess(true, false));
        assertEquals(false, subject.canAccess(true, true));
    }
}
```

## 4. `refactoring_easy_004` — Rename ambiguous distance variable

- úloha: `refactoring`
- náročnosť: `easy`
- tagy: `rename-variable, formatting, readability`

### Celý JSONL záznam

```json
{
  "id": "refactoring_easy_004",
  "task": "refactoring",
  "difficulty": "easy",
  "title": "Rename ambiguous distance variable",
  "input": {
    "kind": "refactoring",
    "class_name": "DistanceFormatter",
    "source_code": "final class DistanceFormatter {\n    String format(int meters) {\n        int x = meters;\n        return x + \" m\";\n    }\n}",
    "focal_method": "format",
    "requirements": "Rename the ambiguous local variable to communicate that it contains meters.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_easy_004/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_easy_004/BehaviorTest.java"
  },
  "expected_process": [
    "identify the ambiguous local identifier",
    "choose a domain-specific name",
    "preserve output formatting"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Rename Variable"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "local identifier x is replaced by a descriptive name"
    ],
    "reference_code": "final class DistanceFormatter {\n    String format(int meters) {\n        int distanceMeters = meters;\n        return distanceMeters + \" m\";\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "identifier_renamed",
      "value": "x"
    }
  ],
  "tags": [
    "rename-variable",
    "formatting",
    "readability"
  ],
  "notes": "Inlining is also behaviorally valid, but a descriptive rename is the target refactoring.",
  "input_code_hash": "54d962d79b8ad12899a460e6aa3f677f1578de72a232c9126d0a599f2098a4a2",
  "normalized_input_code_hash": "26fd4d902124e55c08221142c89b932fc6de6fc1289cfa23115932c2acfcab0e",
  "focal_method_hash": "26fd4d902124e55c08221142c89b932fc6de6fc1289cfa23115932c2acfcab0e"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_004/Input.java`

```java
final class DistanceFormatter {
    String format(int meters) {
        int x = meters;
        return x + " m";
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_easy_004/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesFormattingForBoundaryAndSignedValues() {
        DistanceFormatter subject = new DistanceFormatter();
        assertEquals("0 m", subject.format(0));
        assertEquals("42 m", subject.format(42));
        assertEquals("-3 m", subject.format(-3));
    }
}
```

## 5. `refactoring_medium_001` — Extract percentage discount calculation

- úloha: `refactoring`
- náročnosť: `medium`
- tagy: `extract-method, integer-arithmetic, validation`

### Celý JSONL záznam

```json
{
  "id": "refactoring_medium_001",
  "task": "refactoring",
  "difficulty": "medium",
  "title": "Extract percentage discount calculation",
  "input": {
    "kind": "refactoring",
    "class_name": "PriceCalculator",
    "source_code": "final class PriceCalculator {\n    int finalPrice(int baseCents, int discountPercent) {\n        if (baseCents < 0 || discountPercent < 0 || discountPercent > 100) {\n            throw new IllegalArgumentException(\"invalid price or discount\");\n        }\n        int discount = baseCents * discountPercent / 100;\n        return baseCents - discount;\n    }\n}",
    "focal_method": "finalPrice",
    "requirements": "Extract the discount calculation into a focused helper without changing integer rounding.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_medium_001/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_medium_001/BehaviorTest.java"
  },
  "expected_process": [
    "separate validation from discount arithmetic",
    "extract a named helper",
    "preserve integer rounding and exceptions"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Extract Method"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "new discount helper exists",
      "finalPrice delegates the calculation"
    ],
    "reference_code": "final class PriceCalculator {\n    int finalPrice(int baseCents, int discountPercent) {\n        if (baseCents < 0 || discountPercent < 0 || discountPercent > 100) {\n            throw new IllegalArgumentException(\"invalid price or discount\");\n        }\n        return baseCents - calculateDiscount(baseCents, discountPercent);\n    }\n\n    private int calculateDiscount(int baseCents, int discountPercent) {\n        return baseCents * discountPercent / 100;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "helper_method_exists",
      "value": "calculateDiscount"
    },
    {
      "rule": "focal_method_shorter",
      "value": true
    }
  ],
  "tags": [
    "extract-method",
    "integer-arithmetic",
    "validation"
  ],
  "notes": "Behavior tests pin truncating integer division.",
  "input_code_hash": "edd14c494b477a0d7eda77cd6ebac3bdb985bc157a3ec0227409f305ab866aac",
  "normalized_input_code_hash": "b77ded5b579f8535a6f1a96a1752afa66c27f7f490bcc8c5149d8c7cef5fd3c1",
  "focal_method_hash": "b77ded5b579f8535a6f1a96a1752afa66c27f7f490bcc8c5149d8c7cef5fd3c1"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_001/Input.java`

```java
final class PriceCalculator {
    int finalPrice(int baseCents, int discountPercent) {
        if (baseCents < 0 || discountPercent < 0 || discountPercent > 100) {
            throw new IllegalArgumentException("invalid price or discount");
        }
        int discount = baseCents * discountPercent / 100;
        return baseCents - discount;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_001/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final PriceCalculator subject = new PriceCalculator();

    @Test
    void preservesDiscountAndIntegerRounding() {
        assertEquals(999, subject.finalPrice(999, 0));
        assertEquals(900, subject.finalPrice(1000, 10));
        assertEquals(670, subject.finalPrice(999, 33));
        assertEquals(0, subject.finalPrice(1200, 100));
    }

    @Test
    void preservesValidation() {
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(-1, 10));
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(100, -1));
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(100, 101));
    }
}
```

## 6. `refactoring_medium_002` — Replace nested greeting checks with guards

- úloha: `refactoring`
- náročnosť: `medium`
- tagy: `guard-clause, nullable, nesting`

### Celý JSONL záznam

```json
{
  "id": "refactoring_medium_002",
  "task": "refactoring",
  "difficulty": "medium",
  "title": "Replace nested greeting checks with guards",
  "input": {
    "kind": "refactoring",
    "class_name": "UserGreeting",
    "source_code": "final class UserGreeting {\n    String greet(String name, boolean suspended) {\n        if (name != null) {\n            if (!name.isBlank()) {\n                if (!suspended) {\n                    return \"Hello, \" + name.trim();\n                }\n            }\n        }\n        return \"Unavailable\";\n    }\n}",
    "focal_method": "greet",
    "requirements": "Reduce nesting with guard clauses while preserving null, blank, and suspended behavior.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_medium_002/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_medium_002/BehaviorTest.java"
  },
  "expected_process": [
    "identify all rejection conditions",
    "express them as an early guard",
    "retain the successful greeting path"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Replace Nested Conditional with Guard Clause"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "rejection conditions use an early return",
      "nested depth is reduced"
    ],
    "reference_code": "final class UserGreeting {\n    String greet(String name, boolean suspended) {\n        if (name == null || name.isBlank() || suspended) {\n            return \"Unavailable\";\n        }\n        return \"Hello, \" + name.trim();\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "focal_method_shorter",
      "value": true
    },
    {
      "rule": "boolean_expression_simplified",
      "value": "combined guard"
    }
  ],
  "tags": [
    "guard-clause",
    "nullable",
    "nesting"
  ],
  "notes": "The successful path still trims the name.",
  "input_code_hash": "e128db3c1ffde6ff46654644c2c19ae6315bec7604011cb895f41cf3b8287519",
  "normalized_input_code_hash": "e985bfc0e348a60160e4e24f7edb3bd67111da732ec4a475e9d308f26e3dfdf4",
  "focal_method_hash": "e985bfc0e348a60160e4e24f7edb3bd67111da732ec4a475e9d308f26e3dfdf4"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_002/Input.java`

```java
final class UserGreeting {
    String greet(String name, boolean suspended) {
        if (name != null) {
            if (!name.isBlank()) {
                if (!suspended) {
                    return "Hello, " + name.trim();
                }
            }
        }
        return "Unavailable";
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_002/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final UserGreeting subject = new UserGreeting();

    @Test
    void preservesRejectedInputs() {
        assertEquals("Unavailable", subject.greet(null, false));
        assertEquals("Unavailable", subject.greet("   ", false));
        assertEquals("Unavailable", subject.greet("Ada", true));
    }

    @Test
    void preservesTrimmedGreeting() {
        assertEquals("Hello, Ada", subject.greet("  Ada  ", false));
    }
}
```

## 7. `refactoring_medium_003` — Consolidate delivery handling day

- úloha: `refactoring`
- náročnosť: `medium`
- tagy: `duplicate-fragment, branching, readability`

### Celý JSONL záznam

```json
{
  "id": "refactoring_medium_003",
  "task": "refactoring",
  "difficulty": "medium",
  "title": "Consolidate delivery handling day",
  "input": {
    "kind": "refactoring",
    "class_name": "DeliveryEstimate",
    "source_code": "final class DeliveryEstimate {\n    int estimate(int distanceKm, boolean priority) {\n        int days;\n        if (priority) {\n            days = distanceKm > 100 ? 2 : 1;\n            days += 1;\n        } else {\n            days = distanceKm > 100 ? 5 : 3;\n            days += 1;\n        }\n        return days;\n    }\n}",
    "focal_method": "estimate",
    "requirements": "Move the duplicated handling-day increment out of the conditional branches.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_medium_003/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_medium_003/BehaviorTest.java"
  },
  "expected_process": [
    "identify the identical branch suffix",
    "move it after the conditional",
    "verify priority and distance combinations"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Consolidate Duplicate Conditional Fragments"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "days increment occurs once after the conditional"
    ],
    "reference_code": "final class DeliveryEstimate {\n    int estimate(int distanceKm, boolean priority) {\n        int days;\n        if (priority) {\n            days = distanceKm > 100 ? 2 : 1;\n        } else {\n            days = distanceKm > 100 ? 5 : 3;\n        }\n        days += 1;\n        return days;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "duplication_reduced",
      "value": "days += 1"
    }
  ],
  "tags": [
    "duplicate-fragment",
    "branching",
    "readability"
  ],
  "notes": "The 100 km threshold behavior is explicitly tested.",
  "input_code_hash": "80b4dee8d6ba34a2f2fd01da2f1abd2a7122ce75fd45c368d6f3f883ba0b2f4c",
  "normalized_input_code_hash": "d5c130a96b1be714a3b6dfb6920a347ca3901eec817063f7e6cd15354b4dff9d",
  "focal_method_hash": "d5c130a96b1be714a3b6dfb6920a347ca3901eec817063f7e6cd15354b4dff9d"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_003/Input.java`

```java
final class DeliveryEstimate {
    int estimate(int distanceKm, boolean priority) {
        int days;
        if (priority) {
            days = distanceKm > 100 ? 2 : 1;
            days += 1;
        } else {
            days = distanceKm > 100 ? 5 : 3;
            days += 1;
        }
        return days;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_003/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesPriorityAndDistanceBranches() {
        DeliveryEstimate subject = new DeliveryEstimate();
        assertEquals(2, subject.estimate(100, true));
        assertEquals(3, subject.estimate(101, true));
        assertEquals(4, subject.estimate(100, false));
        assertEquals(6, subject.estimate(101, false));
    }
}
```

## 8. `refactoring_medium_004` — Extract shared tax application

- úloha: `refactoring`
- náročnosť: `medium`
- tagy: `extract-method, collections, duplication`

### Celý JSONL záznam

```json
{
  "id": "refactoring_medium_004",
  "task": "refactoring",
  "difficulty": "medium",
  "title": "Extract shared tax application",
  "input": {
    "kind": "refactoring",
    "class_name": "CartSummary",
    "source_code": "final class CartSummary {\n    int totalWithTax(int[] itemCents, boolean reducedRate) {\n        int total = 0;\n        for (int item : itemCents) {\n            total += item;\n        }\n        if (reducedRate) {\n            int tax = total * 5 / 100;\n            return total + tax;\n        } else {\n            int tax = total * 20 / 100;\n            return total + tax;\n        }\n    }\n}",
    "focal_method": "totalWithTax",
    "requirements": "Remove duplicated tax-and-return logic with a helper while preserving integer rounding.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_medium_004/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_medium_004/BehaviorTest.java"
  },
  "expected_process": [
    "identify duplicated tax application",
    "parameterize the tax rate in a helper",
    "preserve collection summation and rounding"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Extract Method",
      "Remove Duplication"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "one helper applies a supplied tax rate",
      "branch selects only the rate"
    ],
    "reference_code": "final class CartSummary {\n    int totalWithTax(int[] itemCents, boolean reducedRate) {\n        int total = 0;\n        for (int item : itemCents) {\n            total += item;\n        }\n        return applyTax(total, reducedRate ? 5 : 20);\n    }\n\n    private int applyTax(int total, int rate) {\n        return total + total * rate / 100;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "helper_method_exists",
      "value": "applyTax"
    },
    {
      "rule": "duplication_reduced",
      "value": "tax calculation"
    }
  ],
  "tags": [
    "extract-method",
    "collections",
    "duplication"
  ],
  "notes": "Null item arrays remain outside the original contract.",
  "input_code_hash": "defd71e24714c77ec88de299fe79bf6ea6fa8c814e8037ff37831d34aee48297",
  "normalized_input_code_hash": "60f63d63dd33b968922a0db02463b2a153c8c0312058a5f60c5ad9eae020f8bd",
  "focal_method_hash": "60f63d63dd33b968922a0db02463b2a153c8c0312058a5f60c5ad9eae020f8bd"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_004/Input.java`

```java
final class CartSummary {
    int totalWithTax(int[] itemCents, boolean reducedRate) {
        int total = 0;
        for (int item : itemCents) {
            total += item;
        }
        if (reducedRate) {
            int tax = total * 5 / 100;
            return total + tax;
        } else {
            int tax = total * 20 / 100;
            return total + tax;
        }
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_medium_004/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final CartSummary subject = new CartSummary();

    @Test
    void preservesSummationRatesAndIntegerRounding() {
        assertEquals(0, subject.totalWithTax(new int[] {}, true));
        assertEquals(103, subject.totalWithTax(new int[] {33, 66}, true));
        assertEquals(118, subject.totalWithTax(new int[] {33, 66}, false));
        assertEquals(360, subject.totalWithTax(new int[] {100, 200}, false));
    }

    @Test
    void preservesNullFailure() {
        assertThrows(NullPointerException.class, () -> subject.totalWithTax(null, true));
    }
}
```

## 9. `refactoring_tricky_001` — Extract unknown-device risk branch

- úloha: `refactoring`
- náročnosť: `tricky`
- tagy: `extract-method, multi-branch, threshold`

### Celý JSONL záznam

```json
{
  "id": "refactoring_tricky_001",
  "task": "refactoring",
  "difficulty": "tricky",
  "title": "Extract unknown-device risk branch",
  "input": {
    "kind": "refactoring",
    "class_name": "RiskClassifier",
    "source_code": "final class RiskClassifier {\n    String classify(int failedLogins, boolean knownDevice, boolean admin) {\n        if (admin) {\n            if (failedLogins > 0) {\n                return \"REVIEW\";\n            }\n            return \"LOW\";\n        }\n        if (!knownDevice) {\n            if (failedLogins >= 3) {\n                return \"HIGH\";\n            }\n            return \"MEDIUM\";\n        }\n        if (failedLogins >= 5) {\n            return \"HIGH\";\n        }\n        return \"LOW\";\n    }\n}",
    "focal_method": "classify",
    "requirements": "Extract the unknown-device decision into a helper and keep all thresholds and admin behavior unchanged.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_tricky_001/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_tricky_001/BehaviorTest.java"
  },
  "expected_process": [
    "map admin and device-specific branches",
    "extract one cohesive risk decision",
    "verify values around both thresholds"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Extract Method"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "unknown-device branch delegates to a helper",
      "thresholds 3 and 5 are unchanged"
    ],
    "reference_code": "final class RiskClassifier {\n    String classify(int failedLogins, boolean knownDevice, boolean admin) {\n        if (admin) {\n            return failedLogins > 0 ? \"REVIEW\" : \"LOW\";\n        }\n        if (!knownDevice) {\n            return classifyUnknownDevice(failedLogins);\n        }\n        return failedLogins >= 5 ? \"HIGH\" : \"LOW\";\n    }\n\n    private String classifyUnknownDevice(int failedLogins) {\n        return failedLogins >= 3 ? \"HIGH\" : \"MEDIUM\";\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "helper_method_exists",
      "value": "classifyUnknownDevice"
    },
    {
      "rule": "focal_method_shorter",
      "value": true
    }
  ],
  "tags": [
    "extract-method",
    "multi-branch",
    "threshold"
  ],
  "notes": "Negative failed-login counts retain the original low/medium behavior.",
  "input_code_hash": "f3fec4871cbba51ad8aa9fa2e0c993e20b539b679f23a32ec584f07918828990",
  "normalized_input_code_hash": "92444903008a026a451bb7e3dd4c19d09554bea9a3e31d42f12aeb528a0c09ae",
  "focal_method_hash": "92444903008a026a451bb7e3dd4c19d09554bea9a3e31d42f12aeb528a0c09ae"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_001/Input.java`

```java
final class RiskClassifier {
    String classify(int failedLogins, boolean knownDevice, boolean admin) {
        if (admin) {
            if (failedLogins > 0) {
                return "REVIEW";
            }
            return "LOW";
        }
        if (!knownDevice) {
            if (failedLogins >= 3) {
                return "HIGH";
            }
            return "MEDIUM";
        }
        if (failedLogins >= 5) {
            return "HIGH";
        }
        return "LOW";
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_001/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final RiskClassifier subject = new RiskClassifier();

    @Test
    void preservesAdminOverride() {
        assertEquals("LOW", subject.classify(0, false, true));
        assertEquals("REVIEW", subject.classify(1, true, true));
    }

    @Test
    void preservesDeviceSpecificThresholds() {
        assertEquals("MEDIUM", subject.classify(2, false, false));
        assertEquals("HIGH", subject.classify(3, false, false));
        assertEquals("LOW", subject.classify(4, true, false));
        assertEquals("HIGH", subject.classify(5, true, false));
        assertEquals("MEDIUM", subject.classify(-1, false, false));
    }
}
```

## 10. `refactoring_tricky_002` — Flatten booking eligibility checks

- úloha: `refactoring`
- náročnosť: `tricky`
- tagy: `guard-clause, nesting, boundary`

### Celý JSONL záznam

```json
{
  "id": "refactoring_tricky_002",
  "task": "refactoring",
  "difficulty": "tricky",
  "title": "Flatten booking eligibility checks",
  "input": {
    "kind": "refactoring",
    "class_name": "BookingValidator",
    "source_code": "final class BookingValidator {\n    boolean canBook(int requestedSeats, int availableSeats, boolean open) {\n        if (open) {\n            if (requestedSeats > 0) {\n                if (requestedSeats <= availableSeats) {\n                    return true;\n                }\n            }\n        }\n        return false;\n    }\n}",
    "focal_method": "canBook",
    "requirements": "Use guard clauses or an equivalent flat predicate while retaining every rejection condition.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_tricky_002/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_tricky_002/BehaviorTest.java"
  },
  "expected_process": [
    "identify all eligibility conditions",
    "flatten nested branches",
    "test closed, non-positive, insufficient, and exact-capacity cases"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Replace Nested Conditional with Guard Clause"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "nested depth is reduced",
      "all rejection conditions remain explicit"
    ],
    "reference_code": "final class BookingValidator {\n    boolean canBook(int requestedSeats, int availableSeats, boolean open) {\n        if (!open || requestedSeats <= 0 || requestedSeats > availableSeats) {\n            return false;\n        }\n        return true;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "focal_method_shorter",
      "value": true
    },
    {
      "rule": "boolean_expression_simplified",
      "value": "eligibility guard"
    }
  ],
  "tags": [
    "guard-clause",
    "nesting",
    "boundary"
  ],
  "notes": "Returning the combined predicate directly is also valid.",
  "input_code_hash": "fbe7f5b735c1f2e119cb88fdc3e8b4d0e1640da72ffdf28e6c9275bdd0cf5375",
  "normalized_input_code_hash": "356d6277c837f5acb7f0a39ba3bc0cb5a353697af38ce47eae76d758ba96ae99",
  "focal_method_hash": "356d6277c837f5acb7f0a39ba3bc0cb5a353697af38ce47eae76d758ba96ae99"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_002/Input.java`

```java
final class BookingValidator {
    boolean canBook(int requestedSeats, int availableSeats, boolean open) {
        if (open) {
            if (requestedSeats > 0) {
                if (requestedSeats <= availableSeats) {
                    return true;
                }
            }
        }
        return false;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_002/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesEveryEligibilityCondition() {
        BookingValidator subject = new BookingValidator();
        assertEquals(false, subject.canBook(1, 10, false));
        assertEquals(false, subject.canBook(0, 10, true));
        assertEquals(false, subject.canBook(-1, 10, true));
        assertEquals(false, subject.canBook(11, 10, true));
        assertEquals(true, subject.canBook(10, 10, true));
        assertEquals(true, subject.canBook(1, 10, true));
    }
}
```

## 11. `refactoring_tricky_003` — Decompose discount and regional tax

- úloha: `refactoring`
- náročnosť: `tricky`
- tagy: `extract-method, calculation-order, branching`

### Celý JSONL záznam

```json
{
  "id": "refactoring_tricky_003",
  "task": "refactoring",
  "difficulty": "tricky",
  "title": "Decompose discount and regional tax",
  "input": {
    "kind": "refactoring",
    "class_name": "OrderTotal",
    "source_code": "final class OrderTotal {\n    int calculate(int subtotalCents, boolean premium, String country) {\n        if (subtotalCents < 0) {\n            throw new IllegalArgumentException(\"negative subtotal\");\n        }\n        int total = subtotalCents;\n        if (premium) {\n            total = total - total * 10 / 100;\n        }\n        if (\"SK\".equals(country)) {\n            total = total + total * 20 / 100;\n        } else {\n            total = total + total * 10 / 100;\n        }\n        return total;\n    }\n}",
    "focal_method": "calculate",
    "requirements": "Extract discount and tax helpers without reordering integer calculations or changing the public API.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_tricky_003/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_tricky_003/BehaviorTest.java"
  },
  "expected_process": [
    "separate validation, discount, and tax responsibilities",
    "preserve discount-before-tax order",
    "verify premium and country combinations"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Extract Method",
      "Decompose Conditional"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "discount and tax calculations have named helpers",
      "calculation order is unchanged"
    ],
    "reference_code": "final class OrderTotal {\n    int calculate(int subtotalCents, boolean premium, String country) {\n        if (subtotalCents < 0) {\n            throw new IllegalArgumentException(\"negative subtotal\");\n        }\n        int discounted = premium ? applyPremiumDiscount(subtotalCents) : subtotalCents;\n        return applyRegionalTax(discounted, country);\n    }\n\n    private int applyPremiumDiscount(int amount) {\n        return amount - amount * 10 / 100;\n    }\n\n    private int applyRegionalTax(int amount, String country) {\n        int rate = \"SK\".equals(country) ? 20 : 10;\n        return amount + amount * rate / 100;\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "helper_method_exists",
      "value": [
        "applyPremiumDiscount",
        "applyRegionalTax"
      ]
    },
    {
      "rule": "duplication_reduced",
      "value": "tax branches"
    }
  ],
  "tags": [
    "extract-method",
    "calculation-order",
    "branching"
  ],
  "notes": "Integer rounding makes operation order observable and therefore test-covered.",
  "input_code_hash": "11d502a7aecfe4325f2c4ce5729e74ae8c2901f5c4140e8b0f573c718fd7a114",
  "normalized_input_code_hash": "bad1698f4151c99cedb950214d29deda7b7e17010f3e894ce75adab458ad9f66",
  "focal_method_hash": "bad1698f4151c99cedb950214d29deda7b7e17010f3e894ce75adab458ad9f66"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_003/Input.java`

```java
final class OrderTotal {
    int calculate(int subtotalCents, boolean premium, String country) {
        if (subtotalCents < 0) {
            throw new IllegalArgumentException("negative subtotal");
        }
        int total = subtotalCents;
        if (premium) {
            total = total - total * 10 / 100;
        }
        if ("SK".equals(country)) {
            total = total + total * 20 / 100;
        } else {
            total = total + total * 10 / 100;
        }
        return total;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_003/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final OrderTotal subject = new OrderTotal();

    @Test
    void preservesDiscountBeforeTaxAndRounding() {
        assertEquals(1200, subject.calculate(1000, false, "SK"));
        assertEquals(1080, subject.calculate(1000, true, "SK"));
        assertEquals(1098, subject.calculate(999, false, "CZ"));
        assertEquals(990, subject.calculate(999, true, "CZ"));
        assertEquals(1100, subject.calculate(1000, false, null));
    }

    @Test
    void preservesNegativeSubtotalValidation() {
        assertThrows(IllegalArgumentException.class, () -> subject.calculate(-1, false, "SK"));
    }
}
```

## 12. `refactoring_tricky_004` — Extract notification priority policy

- úloha: `refactoring`
- náročnosť: `tricky`
- tagy: `extract-method, boolean, threshold`

### Celý JSONL záznam

```json
{
  "id": "refactoring_tricky_004",
  "task": "refactoring",
  "difficulty": "tricky",
  "title": "Extract notification priority policy",
  "input": {
    "kind": "refactoring",
    "class_name": "NotificationPreference",
    "source_code": "final class NotificationPreference {\n    boolean shouldNotify(boolean enabled, boolean muted, int priority, boolean owner) {\n        if (!enabled) {\n            return false;\n        }\n        if (muted && !owner) {\n            return false;\n        }\n        if (priority >= 8) {\n            return true;\n        }\n        if (owner && priority >= 5) {\n            return true;\n        }\n        return false;\n    }\n}",
    "focal_method": "shouldNotify",
    "requirements": "Extract the priority decision into a named helper while preserving enablement and mute guards.",
    "fixture_path": "data/smoke/refactoring/fixtures/refactoring_tricky_004/Input.java",
    "behavior_test_path": "data/smoke/refactoring/fixtures/refactoring_tricky_004/BehaviorTest.java"
  },
  "expected_process": [
    "separate global guards from priority eligibility",
    "extract a descriptive priority predicate",
    "verify owner and threshold edge cases"
  ],
  "expected_output": {
    "kind": "refactoring",
    "expected_refactoring_types": [
      "Extract Method",
      "Simplify Conditional"
    ],
    "must_compile": true,
    "must_preserve_behavior": true,
    "must_preserve_public_api": true,
    "structural_expectations": [
      "enablement and mute guards remain",
      "priority policy is named in a helper"
    ],
    "reference_code": "final class NotificationPreference {\n    boolean shouldNotify(boolean enabled, boolean muted, int priority, boolean owner) {\n        if (!enabled || (muted && !owner)) {\n            return false;\n        }\n        return hasNotificationPriority(priority, owner);\n    }\n\n    private boolean hasNotificationPriority(int priority, boolean owner) {\n        return priority >= 8 || (owner && priority >= 5);\n    }\n}"
  },
  "validation_rules": [
    {
      "rule": "code_compiles",
      "value": null
    },
    {
      "rule": "behavior_tests_pass",
      "value": null
    },
    {
      "rule": "public_api_preserved",
      "value": null
    },
    {
      "rule": "helper_method_exists",
      "value": "hasNotificationPriority"
    },
    {
      "rule": "boolean_expression_simplified",
      "value": "priority policy"
    }
  ],
  "tags": [
    "extract-method",
    "boolean",
    "threshold"
  ],
  "notes": "Owner bypasses mute but still needs priority 5; non-owner needs priority 8.",
  "input_code_hash": "0d6331972bfb66ee735bd47ba0ff21775df01f2a5391a082133235b6740dda87",
  "normalized_input_code_hash": "24f268d3a44080e2db0bff8d7019a902558b8bc9f9ab3800b5edb68e1bbaf083",
  "focal_method_hash": "24f268d3a44080e2db0bff8d7019a902558b8bc9f9ab3800b5edb68e1bbaf083"
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_004/Input.java`

```java
final class NotificationPreference {
    boolean shouldNotify(boolean enabled, boolean muted, int priority, boolean owner) {
        if (!enabled) {
            return false;
        }
        if (muted && !owner) {
            return false;
        }
        if (priority >= 8) {
            return true;
        }
        if (owner && priority >= 5) {
            return true;
        }
        return false;
    }
}
```

### Celý `data/smoke/refactoring/fixtures/refactoring_tricky_004/BehaviorTest.java`

```java
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final NotificationPreference subject = new NotificationPreference();

    @Test
    void preservesGlobalGuards() {
        assertEquals(false, subject.shouldNotify(false, false, 10, true));
        assertEquals(false, subject.shouldNotify(true, true, 10, false));
    }

    @Test
    void preservesOwnerAndPriorityThresholds() {
        assertEquals(false, subject.shouldNotify(true, false, 7, false));
        assertEquals(true, subject.shouldNotify(true, false, 8, false));
        assertEquals(false, subject.shouldNotify(true, false, 4, true));
        assertEquals(true, subject.shouldNotify(true, false, 5, true));
        assertEquals(true, subject.shouldNotify(true, true, 5, true));
    }
}
```
