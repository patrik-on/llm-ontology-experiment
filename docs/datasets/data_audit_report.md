# Audit dát a datasetov projektu LLM Ontology Experiment

**Stav k:** 23. augustu 2026  
**Účel:** podklad pre diplomovú prácu, konzultácie s vedúcim práce a reprodukovateľné reportovanie experimentov  
**Rozsah:** zdrojové datasety, naše odvodené splity, fine-tuningové dáta, retrieval korpusy, Chroma indexy, smoke dataset a plánované externé benchmarky

## 1. Manažérske zhrnutie

Projekt pracuje s tromi hlavnými externými zdrojmi dát:

1. **Methods2Test** pre generovanie JUnit testov,
2. **ML4Refactoring** pre refaktoring Java kódu,
3. **MaRV** ako menší refaktoringový zdroj s manuálnymi hodnoteniami.

Z týchto zdrojov vytvárame tri hlavné experimentálne datasety:

- `testing`: 4 000 / 500 / 500 záznamov z Methods2Test,
- `refactoring`: 4 478 / 600 / 608 záznamov, pričom ide o spojenie ML4Refactoring a MaRV,
- `combined`: 8 000 / 1 000 / 1 000 záznamov, presne 50 % Methods2Test a 50 % ML4Refactoring; MaRV v ňom nie je.

Okrem nich používame ručne vytvorený `handcrafted_smoke_v1` s 24 prípadmi na kontrolu pipeline. Nie je určený na tréning ani retrieval. TestBench a SWE-Refactor sú nakonfigurované ako budúce externé benchmarky, ale ich dáta sa v aktuálnom pracovnom priestore nenachádzajú a plná benchmarková evaluácia ešte nie je dokončená.

Audit potvrdil, že základná schéma, počty súborov, hashovanie manifestov a zákaz indexovania testovacích dát sú implementované dobre. Zároveň však odhalil niekoľko závažných dátových rizík, ktoré treba vyriešiť pred tým, ako budú výsledky prezentované ako finálne:

- Methods2Test subset je **prvý validný lexikografický výrez**, nie náhodná alebo reprezentatívna vzorka. Napríklad 500 validačných záznamov pochádza iba zo 6 projektov a 384 z nich z jedného projektu.
- Materializovaný ML4Refactoring split obsahuje **identické páry a rovnaké projekty/commity naprieč train, val a test**. Medzi train a test je 188 identických before/after párov.
- Z 4 000 ML4Refactoring train záznamov je 1 325 riadkov nadbytočných exact-pair duplikátov a 624 záznamov má typ refaktoringu `unknown`.
- MaRV poskytuje manuálne hlasy, ale aktuálna pipeline ich iba uloží; **nefiltruje podľa kvality**. Zo 686 použitých MaRV záznamov má iba 321 súhlas oboch hodnotiteľov, zatiaľ čo 79 je oboma hodnotiteľmi označených ako nesúhlas a zvyšok je konfliktný, neurčitý alebo hodnotený iba raz.
- Aktuálny kód už deklaruje group-aware splitovanie, no lokálne JSONL súbory zodpovedajú staršej príprave. Kód a materializované dáta preto nie sú úplne synchronizované.
- Shared dataset je vyvážený **počtom riadkov**, nie objemom tokenov. Pri train splite má ML4Refactoring priemerne približne 1 656 prompt+output tokenov na príklad, Methods2Test približne 284. Pred truncation tak refactoring tvorí približne 85 % tokenového objemu shared datasetu.
- Pri limite 2 048 tokenov sa skracuje 1 327 zo 4 000 ML4Refactoring train príkladov (33,17 %) a 162 cieľových výstupov je priamo skrátených.
- Retrieval pipeline riziko voči finálnemu test splitu dodatočne filtruje. Z pôvodných 4 478 refactoring train záznamov ostáva iba 2 043 leakage-safe kandidátov a po obsahovej deduplikácii 1 761 indexovaných dokumentov.
- Refactoring manifest sa volá `ml4refactoring_retrieval`, hoci jeho zdrojový súbor obsahuje ML4Refactoring **aj MaRV**. Názov preto nevyjadruje úplnú provenienciu.
- Smoke leakage report je naviazaný na staršie manifest ID retrieval korpusu; lokálny aktívny index je `ollama_bge_m3_v3`. Audit treba po zmene indexu obnoviť.

**Odporúčaný status dát:** aktuálne dáta sú vhodné na vývoj pipeline, smoke testy a exploratívne experimenty. Pred finálnou tréningovou a benchmarkovou kapitolou treba datasety znovu vytvoriť podľa opraveného, verziovaného protokolu a následne modely pretrénovať a prehodnotiť.

## 2. Čo presne považujeme za „dáta“

Audit rozlišuje päť vrstiev:

```text
Externý zdroj
    ↓
Raw lokálna kópia
    ↓ čistenie, výber, normalizácia, split
Processed JSONL
    ├── fine-tuning a interná evaluácia
    └── leakage filtering → retrieval korpus → Chroma index

Samostatne:
handcrafted smoke prípady → iba pipeline/smoke evaluácia
externé benchmarky → finálna nezávislá evaluácia, zatiaľ neprítomné
```

Výsledky modelov, predikcie, metriky a LoRA adaptéry sú experimentálne artefakty, nie vstupné datasety. Sú dôležité pre reprodukovateľnosť, ale tento dokument ich neaudituje ako zdrojové dáta.

## 3. Inventár všetkých dátových zdrojov

| Zdroj alebo odvodený dataset | Stav | Veľkosť / počet | Hlavná rola |
|---|---:|---:|---|
| Methods2Test raw | lokálne prítomný | 780 944 párov podľa autora | externý zdroj testing dát |
| ML4Refactoring `all.zip` | lokálne prítomný | 40 783 884 999 B; 11 150 lokálnych project ZIPov | externý zdroj refactoring dát |
| MaRV `MaRV.json` | lokálne prítomný | 698 lokálnych záznamov | externý manuálne hodnotený refactoring zdroj |
| `processed/testing` | prítomný | 4 000 / 500 / 500 | B2-T tréning, validácia, test; testing retrieval |
| `processed/refactoring_ml4ref` | prítomný | 4 000 / 500 / 500 | ML4Ref zložka refactoring dát |
| `processed/refactoring_marv` | prítomný | 478 / 100 / 108 | MaRV zložka refactoring dát |
| `processed/refactoring` | prítomný | 4 478 / 600 / 608 | B2-R tréning, validácia, test; refactoring retrieval |
| `processed/combined` | prítomný | 8 000 / 1 000 / 1 000 | B1 shared fine-tuning |
| leakage-safe testing retrieval | prítomný | 3 986 záznamov | vstup do `testing_db` |
| leakage-safe refactoring retrieval | prítomný | 2 043 záznamov | vstup do `refactoring_db` |
| Chroma `testing_db` | prítomný vo V3 | 3 978 unikátnych dokumentov | testing RAG |
| Chroma `refactoring_db` | prítomný vo V3 | 1 761 unikátnych dokumentov | refactoring RAG |
| Chroma `mixed` | prítomný vo V3 | 5 739 unikátnych dokumentov | single-collection RAG |
| `handcrafted_smoke_v1` | prítomný | 24 prípadov | smoke/regresná evaluácia |
| TestBench | iba config a adaptér | očakávaných 108 prípadov | budúci testing benchmark |
| SWE-Refactor | iba config a adaptér | očakávaných 1 099 prípadov | budúci refactoring benchmark |
| literatúra / `data/external` | nepoužíva sa | 0 schválených zdrojov | potenciálny budúci RAG zdroj |

## 4. Spoločná processed schéma

Všetky fine-tuningové JSONL záznamy majú minimálne:

| Pole | Kto ho pridáva | Význam |
|---|---|---|
| `instruction` | náš preprocessing | text úlohy pre model |
| `input` | prevzaté a normalizované | vstupný Java kód alebo diff |
| `output` | prevzaté a normalizované | očakávaný JUnit/refaktorovaný kód |
| `domain` | náš preprocessing | `testing` alebo `refactoring` |
| `source` | náš preprocessing | `methods2test`, `ml4refactoring` alebo `marv` |

Zdrojovo špecifické metadata:

| Dataset | Polia v aktuálnych materializovaných JSONL |
|---|---|
| Methods2Test | `context_level`, `source_file` |
| ML4Refactoring | `project`, `commit_sha`, `file_path`, `refactoring_type` |
| MaRV | `refactoring_type`, `refactoring_id`, `commit_sha`, `commit_link`, `file_path`, `description`, `evaluation_votes` |

Dôležitý detail: súčasná implementácia Methods2Test už generuje aj `project` a `repository` a súčasná MaRV implementácia generuje `repository`. Tieto polia však v existujúcich processed JSONL chýbajú. Identita sa preto pri Methods2Test spätne odvodzuje z `source_file`; pri MaRV je v dátach iba `commit_link`. Ide o dôkaz, že materializované dáta boli pripravené staršou verziou preprocessingu.

Inštrukcie pridávame my a sú v slovenčine:

- testing: `Vygeneruj JUnit test pre nasledujúcu Java metódu.`,
- refactoring: `Vygeneruj refaktorovanú verziu ... podľa typu refaktoringu: <typ>.`

Pôvodné zdroje tieto instruction-tuning inštrukcie neposkytujú. Externé benchmark adaptéry a handcrafted smoke dáta používajú prevažne anglické inštrukcie a požiadavky. Jazyk promptu je preto ďalšia experimentálna premenná, ktorú treba buď zjednotiť, alebo explicitne reportovať.

## 5. Methods2Test

### 5.1 Čo poskytuje pôvodný dataset

[Methods2Test](https://github.com/microsoft/methods2test) je supervised dataset párujúci Java JUnit test case s jeho focal method, teda metódou, ktorú test pravdepodobne overuje. Autori mapovanie zostavili heuristikami založenými najmä na názvoch testov a metód a na unikátnom volaní metódy z focal class. Dataset je detailne opísaný v práci [Methods2Test: A dataset of focal methods mapped to test cases](https://arxiv.org/abs/2203.12776).

Pôvodný dataset deklaruje:

| Split | Repozitáre | Páry |
|---|---:|---:|
| train | 7 440 | 624 022 |
| validation | 953 | 78 534 |
| test | 1 017 | 78 388 |
| **spolu** | **9 410** | **780 944** |

Zdrojové projekty boli vybrané zo 91 385 analyzovaných Java repozitárov. Oficiálne splity sú repository-disjoint a autori deklarujú odstránenie duplicitných párov s rovnakou reprezentáciou kódu.

Raw dataset obsahuje bohatšie štruktúrované údaje:

- informácie o repozitári,
- focal class a focal method,
- test class a test case,
- signatúry, parametre, modifikátory, telo, invokácie a cesty k súborom,
- paralelný korpus pri rôznej úrovni kontextu.

Päť dostupných úrovní focal contextu je:

1. `src_fm`: iba focal method,
2. `src_fm_fc`: focal method + názov focal class,
3. `src_fm_fc_co`: navyše konštruktory,
4. `src_fm_fc_ms`: navyše verejné metódy,
5. `src_fm_fc_ms_ff`: navyše verejné polia.

### 5.2 Čo z neho berieme my

Používame iba `corpus/json` a iba pole `src_fm`. Cieľom je jednoduché mapovanie:

```text
input  = samotná focal method
output = pôvodný developer-written test case (`target`)
```

Pole `target` teda **reálne používame**, ale jeho rola závisí od fázy:

- pri fine-tuningu je cieľovou odpoveďou, z ktorej sa počíta tréningový loss;
- pri internej evaluácii je referenciou na porovnanie s predikciou a model ho
  nedostáva v samotnom vstupnom zadaní;
- pri RAG-u zostáva súčasťou uloženého input/output príkladu a po retrievali
  môže slúžiť ako developer-written demonštrácia. Aktuálna V3 embedding šablóna
  však vyhľadávací vektor počíta iba zo vstupného production code, nie z
  referenčného testu.

Jeden celý raw záznam so všetkými šiestimi poľami je uvedený bez skrátenia v
`docs/datasets/raw_record_examples.md`.

Pre každý oficiálny split sa súbory zoradia podľa cesty a berú sa prvé validné príklady, kým sa nenaplní limit:

| Náš split | Prečítané raw súbory | Preskočené | Uložené |
|---|---:|---:|---:|
| train | 4 181 | 181 | 4 000 |
| val z oficiálneho `eval` | 507 | 7 | 500 |
| test | 523 | 23 | 500 |

Validácia ponechá príklad iba vtedy, ak:

- input aj output sú neprázdne reťazce,
- input má 50 až 4 000 znakov,
- output má 50 až 6 000 znakov,
- output obsahuje aspoň jeden marker testu alebo assertion, napr. `@Test`, `assert`, `Assertions.` alebo `fail(`.

Ďalej dopĺňame:

- slovenskú inštrukciu,
- `domain=testing`,
- `source=methods2test`,
- `context_level=src_fm`,
- `source_file` ako provenienciu.

### 5.3 Ako ho používame

| Použitie | Konkrétny súbor |
|---|---|
| B2-T fine-tuning | `data/processed/testing/train.jsonl` |
| B2-T výber najlepšieho checkpointu | `data/processed/testing/val.jsonl` |
| interná testing evaluácia | `data/processed/testing/test.jsonl` |
| B1 shared fine-tuning | testing polovica `data/processed/combined/*` |
| testing RAG | leakage-safe derivát z testing `train.jsonl` |

Pre testing úlohu je dataset vhodný preto, že poskytuje reálne developer-written testy a explicitný focal-method → test vzťah. Nejde o syntetické testy generované coverage nástrojom.

### 5.4 Reálny profil nášho výrezu

| Split | Priemerný input | Priemerný output | Medián input/output | Počet projektov vo výreze |
|---|---:|---:|---:|---:|
| train | 563,89 zn. | 500,71 zn. | 343 / 315 | 66 |
| val | 456,49 zn. | 359,01 zn. | 218 / 288 | 6 |
| test | 411,88 zn. | 379,63 zn. | 267 / 278 | 18 |

Koncentrácia je vysoká:

- najväčší train projekt dáva 804 z 4 000 príkladov (20,10 %),
- najväčší validation projekt dáva 384 z 500 príkladov (76,80 %),
- najväčší test projekt dáva 78 z 500 príkladov (15,60 %).

Spracovaný dataset tak pokrýva iba 90 project ID z pôvodných 9 410 repozitárov a približne 0,64 % všetkých párov. Samotná malá veľkosť nie je problém, ale lexikografický výber vytvára nevysvetlený selection bias.

### 5.5 Duplicity a leakage

V train splite:

- 2 297 riadkov opakuje input focal method,
- 33 riadkov opakuje output,
- iba 8 riadkov je nadbytočný exact input+output pár.

Opakovaný input nemusí byť chyba: jedna focal method môže mať viac legitímnych test cases. Pri súčasnom formáte však rovnaký prompt vedie k viacerým rôznym referenciám, čo treba pri tréningu aj textovej evaluácii interpretovať ako one-to-many problém.

Naprieč train a test je jeden rovnaký exact input, ale nie celý rovnaký pár. Konzervatívny retrieval audit navyše našiel 14 normalizovaných code-fingerprint konfliktov s test benchmarkom; všetkých 14 bolo pred indexovaním vyradených.

Oficiálne repository-level splity zostávajú podľa `source_file` oddelené. To je pozitívne, ale výber projektov je príliš úzky a nerovnomerný.

### 5.6 Hlavné obmedzenia

- Focal-method mapovanie je heuristické, nie manuálne garantované.
- Používame iba najmenší kontext `src_fm`; model nevidí triedu, importy, konštruktory ani závislosti.
- Output býva iba test method, nie kompletná kompilovateľná test class.
- Assertion marker kontroluje prítomnosť textu, nie kompiláciu alebo správnosť testu.
- Výber prvých validných súborov nie je reprezentatívny sampling.
- Projektová identita nie je v materializovanom JSONL samostatným poľom.

## 6. ML4Refactoring

### 6.1 Čo poskytuje pôvodný dataset

[ML4Refactoring na Zenodo](https://zenodo.org/records/3547639) poskytuje:

- `all.zip` so zdrojovým kódom pred a po refaktoringu,
- `refactoring50` so štrukturálnymi metrikami,
- zoznam analyzovaných projektov.

Súvisiaca práca [The Effectiveness of Supervised Machine Learning Algorithms in Predicting Software Refactoring](https://arxiv.org/abs/2001.03338) uvádza viac než dva milióny refaktoringov z 11 149 projektov ekosystémov Apache, F-Droid a GitHub a 20 typov refaktoringu na úrovni tried, metód a premenných.

Pôvodný vedecký účel je predikcia refactoring opportunities. My dataset repurposujeme na code-to-code generation z before/after súborov. Toto je metodická zmena úlohy a musí byť v práci explicitne uvedená.

Lokálna kópia má 40 783 884 999 bajtov a rozbalený `dataset` obsahuje 11 150 ZIP archívov projektov. Zenodo uvádza MD5 `0e26e937b40534466e72724f1aefecda`; tento audit 40 GB lokálny súbor nanovo nehashoval.

### 6.2 Čo z neho berieme my

Nepoužívame štrukturálne metriky ani projektový spreadsheet. Používame iba before/after Java súbory z projektových ZIPov.

Preprocessing:

1. zoradí project ZIPy lexikograficky,
2. v každom projekte nájde `before-refactoring` a `after-refactoring`,
3. spáruje Java súbory s rovnakou relatívnou cestou,
4. z názvu súboru substring heuristikou odhadne typ refaktoringu,
5. ponechá iba rozdielne, neprázdne páry s dĺžkou 50 až 12 000 znakov na každej strane,
6. doplní instruction-tuning polia a metadata,
7. zastaví zber po dosiahnutí 5 000 záznamov.

Dopĺňané metadata sú `project`, `commit_sha`, `file_path` a `refactoring_type`. Input a output sú často celý Java súbor, nie iba zmenená metóda.

### 6.3 Ako ho používame

| Použitie | Rozsah |
|---|---|
| B2-R | 4 000/500/500 ML4Ref záznamov plus MaRV |
| B1 shared | presne 4 000/500/500 ML4Ref záznamov; bez MaRV |
| refactoring RAG | leakage-safe derivát z finálneho mixed refactoring train splitu |
| interná refactoring evaluácia | ML4Ref časť finálneho test splitu |

Dôvod použitia je veľkosť, reálne historické before/after transformácie a širšie pokrytie refaktoringových typov než MaRV. Nevýhodou je, že zdroj nebol vytvorený ako generatívny benchmark a jeden commit alebo súbor môže obsahovať aj ďalšie zmeny.

### 6.4 Reálny profil nášho 5 000-záznamového subsetu

Subset pochádza iba zo 17 projektov, teda približne z 0,15 % projektov deklarovaných pôvodným datasetom. Zastavenie po prvých 5 000 validných záznamoch výrazne zvýhodňuje abecedne skoré Apache projekty.

Najväčšie train zdroje:

| Projekt | Train záznamy | Podiel train |
|---|---:|---:|
| accumulo | 1 558 | 38,95 % |
| activemq | 541 | 13,53 % |
| abdera | 541 | 13,53 % |
| activemq-apollo | 468 | 11,70 % |
| ace | 405 | 10,13 % |

Tieto projekty spolu tvoria 87,83 % ML4Ref train splitu.

Typy vo všetkých 5 000 záznamoch:

| Typ | Počet | Podiel |
|---|---:|---:|
| Move Class | 1 777 | 35,54 % |
| `unknown` | 791 | 15,82 % |
| Rename Method | 537 | 10,74 % |
| Pull Up Method | 465 | 9,30 % |
| Extract Method | 411 | 8,22 % |
| Rename Variable | 329 | 6,58 % |
| Move Method | 185 | 3,70 % |
| Rename Class | 150 | 3,00 % |
| Push Down Method | 124 | 2,48 % |
| Extract Superclass | 81 | 1,62 % |
| Inline Method | 66 | 1,32 % |
| Extract Class | 63 | 1,26 % |
| Extract Interface | 21 | 0,42 % |

`unknown` nevzniká nutne chybou zdroja. Parser nepokrýva viacero názvov prítomných v dátach, napríklad `Rename Parameter`, `Extract Variable`, `Inline Variable` alebo `Extract Subclass`. Model potom dostáva inštrukciu „typ refaktoringu: unknown“, čím sa stráca dôležitý supervision signal.

Dĺžky sú výrazne vyššie než pri Methods2Test:

| Split | Priemerný input | Priemerný output | P95 input/output |
|---|---:|---:|---:|
| train | 4 293,25 zn. | 3 733,09 zn. | 10 453 / 10 059 |
| val | 4 362,52 zn. | 3 788,67 zn. | 10 576 / 10 164 |
| test | 4 523,65 zn. | 3 933,69 zn. | 10 916 / 10 824 |

### 6.5 Duplicity a cross-split leakage

V train splite je:

- 1 354 nadbytočných opakovaní inputu,
- 1 354 nadbytočných opakovaní outputu,
- 1 325 nadbytočných exact input+output párov.

To znamená, že iba 2 675 zo 4 000 train riadkov má unikátny exact pár. Duplikáty zvyšujú váhu opakovaných príkladov bez explicitného experimentálneho dôvodu.

Naprieč splitmi:

| Porovnanie | Rovnaký input | Rovnaký exact pár | Spoločné projekty | Spoločné commity |
|---|---:|---:|---:|---:|
| train vs val | 191 | 187 | 12 | 208 |
| train vs test | 197 | 188 | 11 | 224 |
| val vs test | 50 | 49 | 10 | 104 |

Tento stav znehodnocuje test split ako nezávislý od fine-tuningu. Súčasná implementácia už obsahuje project-aware delenie, ale aktuálne JSONL súbory zjavne vznikli staršou record-level stratégiou. Finálne tvrdenia preto nemajú používať tento test split bez regenerácie.

### 6.6 Tokenizácia a truncation

Audit bol vykonaný presným tokenizerom `Qwen/Qwen2.5-Coder-7B-Instruct` a tréningovým prompt formátom. Modelová konfigurácia má `max_seq_length=2048`. Ak sa prompt a output nezmestia, implementácia prioritizuje začiatok outputu a ponecháva iba koniec promptu.

| Split | Priemer prompt tokenov | Priemer output tokenov | Nad 2 048 | Skrátený output |
|---|---:|---:|---:|---:|
| train | 907,8 | 748,3 | 1 327 (33,17 %) | 162 |
| val | 923,1 | 759,4 | 169 (33,80 %) | 22 |
| test | 957,7 | 792,8 | 174 (34,80 %) | 30 |

Pri 488 train prípadoch ostane po truncation z promptu najviac 128 tokenov. Keďže prompt sa skracuje zľava, môže vypadnúť inštrukcia, začiatok triedy, package alebo relevantná časť pôvodného kódu. Toto je nielen technický detail, ale vlastnosť skutočných tréningových dát.

## 7. MaRV

### 7.1 Čo poskytuje pôvodný dataset

[MaRV](https://zenodo.org/records/14450098) je manuálne validovaný dataset štyroch typov refaktoringu: Extract Method, Rename Method, Rename Variable a Remove Parameter. Práca [MaRV: A Manually Validated Refactoring Dataset](https://labsoft-ufmg.github.io/publications/2025/forge2025preprint.pdf) opisuje 693 párov zo 126 Java repozitárov. Každý z týchto 693 párov hodnotili dvaja rôzni hodnotitelia z celkového poolu 40 účastníkov.

Hodnotitelia odpovedali, či before/after pár skutočne reprezentuje uvedený typ refaktoringu:

- `1` = agree,
- `0` = disagree,
- `-1` = I don't know.

Publikovaný článok uvádza 321 prípadov `[agree, agree]`, 84 `[disagree, disagree]`, 285 konfliktných a 3 `[I don't know, I don't know]`. Päť prípadov hodnotených iba jedným človekom bolo z publikovaných 693 vylúčených.

### 7.2 Rozdiel medzi publikovaným a lokálnym raw súborom

Lokálny `MaRV.json` obsahuje 698, nie 693 záznamov:

| Typ | Lokálny raw počet |
|---|---:|
| Extract Method | 173 |
| Rename Method | 176 |
| Rename Variable | 174 |
| Remove Parameter | 175 |
| **Spolu** | **698** |

Súbor obsahuje aj päť one-vote prípadov. To zodpovedá rozdielu medzi 698 lokálnymi a 693 publikovanými prípadmi. Raw SHA-256 lokálnej kópie je `d2d8171d3f3c0d19d1bbfbf7d606add9369a74b2f23fd28d7ca14bf1ec224828`.

### 7.3 Čo z neho berieme my

Pipeline načíta štyri podporované typy, skontroluje neprázdnosť a dĺžku 50 až 12 000 znakov a uloží:

- `code_before` ako `input`,
- `code_after` ako `output`,
- slovenskú refactoring inštrukciu,
- refactoring a commit metadata,
- všetky dostupné `evaluation_votes`.

Po dĺžkovom filtri ostáva 686 záznamov:

| Typ | Uložené |
|---|---:|
| Extract Method | 171 |
| Rename Method | 173 |
| Rename Variable | 170 |
| Remove Parameter | 172 |

Rozdelenie je 478 / 100 / 108. Aktuálny kód už používa commit-aware group split, ale materializované súbory majú malé commit overlap: 2 commity medzi train/val a 2 medzi val/test. Exact páry sa medzi splitmi neopakujú.

### 7.4 Kvalita manuálnych hodnotení v skutočne použitých 686 záznamoch

| Stav hlasov | Počet | Podiel |
|---|---:|---:|
| obaja súhlasia `(1,1)` | 321 | 46,79 % |
| obaja nesúhlasia `(0,0)` | 79 | 11,52 % |
| obaja nevedia `(-1,-1)` | 3 | 0,44 % |
| konfliktné dva hlasy | 278 | 40,52 % |
| iba jeden hlas | 5 | 0,73 % |

Kritický fakt je, že preprocessing podľa hlasov **nič nevylučuje**. Všetkých 686 párov sa používa ako pozitívna ukážka požadovaného refaktoringu, vrátane 79 prípadov, ktoré obaja hodnotitelia označili ako nesprávnu reprezentáciu, a 286 prípadov bez pozitívneho konsenzu.

### 7.5 Ako ho používame a prečo

MaRV sa pridáva do B2-R, aby refactoring dataset doplnil o menší, ručne hodnotený zdroj a štyri jasne pomenované typy. Reálne pomery sú:

| Split finálneho refactoring datasetu | ML4Refactoring | MaRV |
|---|---:|---:|
| train 4 478 | 4 000 (89,33 %) | 478 (10,67 %) |
| val 600 | 500 (83,33 %) | 100 (16,67 %) |
| test 608 | 500 (82,24 %) | 108 (17,76 %) |

MaRV nie je súčasťou B1 shared datasetu. Dokumentácia explicitne definuje shared mix ako 4 000 Methods2Test + 4 000 ML4Refactoring, ale neuvádza samostatné vedecké zdôvodnenie vylúčenia MaRV. Metodicky sa dá chápať ako snaha zachovať presne 50:50 doménový a zdrojový mix, toto však treba v práci označiť ako rozhodnutie autora experimentu, nie vlastnosť datasetu.

MaRV príklady sú kratšie a truncation riziko je výrazne menšie než pri ML4Refactoring: nad limit 2 048 tokenov je 18 zo 478 train príkladov (3,77 %) a žiadny MaRV train output sa samostatne neskracuje.

## 8. Naše finálne odvodené datasety

### 8.1 `refactoring`

Pre každý split sa ML4Refactoring a MaRV spoja a deterministicky premiešajú so seedom 42. Audit potvrdil, že každý výsledný split je presne multisetovým súčtom príslušných zdrojových splitov; nepridávajú sa nové syntetické príklady.

Celkový refactoring dataset má 5 686 záznamov. Typové rozdelenie:

| Typ | Počet | Podiel |
|---|---:|---:|
| Move Class | 1 777 | 31,25 % |
| `unknown` | 791 | 13,91 % |
| Rename Method | 710 | 12,49 % |
| Extract Method | 582 | 10,24 % |
| Rename Variable | 499 | 8,78 % |
| Pull Up Method | 465 | 8,18 % |
| Move Method | 185 | 3,25 % |
| Remove Parameter | 172 | 3,02 % |
| ostatné typy spolu | 505 | 8,88 % |

Tokenizačný audit finálneho refactoring train splitu:

- priemer promptu 863,3 tokenu,
- priemer outputu 719,0 tokenu,
- 1 345 z 4 478 príkladov (30,04 %) prekračuje 2 048 tokenov,
- 162 outputov je skrátených.

### 8.2 `combined`

Combined dataset je presne:

```text
train = 4 000 Methods2Test + 4 000 ML4Refactoring
val   =   500 Methods2Test +   500 ML4Refactoring
test  =   500 Methods2Test +   500 ML4Refactoring
```

Každý split sa premieša seedom 42. MaRV sa nepridáva.

Tým dosahujeme 50:50 pomer podľa počtu príkladov. Nejde však o vyváženie podľa tokenov:

- Methods2Test train má v priemere 159,7 prompt + 124,0 output tokenu,
- ML4Refactoring train má v priemere 907,8 prompt + 748,3 output tokenu,
- ML4Refactoring preto tvorí približne 85 % pred-truncation tokenového objemu oboch rovnakopočetných polovíc.

V combined train splite prekračuje limit 1 328 z 8 000 záznamov (16,60 %); prakticky všetky pochádzajú z ML4Refactoring. Record-level balance preto neznamená rovnaký tréningový vplyv domén.

Zároveň B1 shared model vidí 8 000 train príkladov, kým B2-T 4 000 a B2-R 4 478. Porovnanie shared vs specialist modelov je teda ovplyvnené aj rozdielnym počtom tréningových záznamov. Výsledok nemožno interpretovať iba ako čistý efekt zdieľania znalostí bez size ablation alebo kontrolovaného token budgetu.

## 9. Retrieval dáta a Chroma indexy

### 9.1 Ktoré dáta smú do retrievalu

Indexovať sa smie iba train materiál. Validation, test, smoke a budúce benchmarky majú `allowed_for_indexing=false` alebo sú explicitne vylúčené.

Pred indexovaním pipeline:

1. overí hash a počet manifestu,
2. rezervuje identity benchmark/test splitu,
3. vyradí kolidujúce group identity,
4. vyradí normalizované code fingerprints,
5. znova vykoná group a fingerprint audit,
6. až potom vytvorí embedding dokumenty.

### 9.2 Čo sa vyradí

| Doména | Pôvodný train | Identity filter | Fingerprint filter | Ostáva |
|---|---:|---:|---:|---:|
| testing | 4 000 | 0 | 14 | 3 986 |
| refactoring | 4 478 | 2 382 | 53 | 2 043 |

Refactoring filter vyradí 54,38 % pôvodného train splitu. Nie je to náhodná strata; priamo odhaľuje, že train a test zdieľajú veľké množstvo identít na zvolenej úrovni.

Zdrojové zloženie refactoring retrievalu sa pritom mení:

| Fáza | ML4Refactoring | MaRV | Spolu |
|---|---:|---:|---:|
| pôvodný refactoring train | 4 000 | 478 | 4 478 |
| po leakage filtri | 1 565 | 478 | 2 043 |
| po obsahovej deduplikácii | 1 283 | 478 | 1 761 |

Všetkých 478 MaRV train záznamov prejde do finálneho refactoring indexu. MaRV tak tvorí 27,14 % indexovaných refactoring dokumentov, hoci v pôvodnom train splite tvoril iba 10,67 %. Keďže vote policy nefiltruje nekonsenzuálne a negatívne MaRV príklady, problém sa neprenáša iba do fine-tuningu, ale aj do evidencie poskytovanej RAG modelu. V indexe navyše ostáva približne 308 unikátnych dokumentov s typom `unknown`.

Manifest deklaruje pre refactoring `primary_group_level: method`, ale ML4Refactoring záznamy nemajú `refactoring_id`, `method_id` ani `case_id`. Reálna group key sa preto pri nich zredukuje na project+commit. Názov „method-level“ je teda pre ML4Refactoring presnejšie konzervatívny commit-level filter.

### 9.3 Čo sa indexuje

V lokálnom V3 indexe (`bge-m3`, 1 024 rozmerov, cosine, normalizované vektory):

| Kolekcia | Prijaté po leakage filtri | Indexované unikátne | Obsahové duplikáty |
|---|---:|---:|---:|
| `testing_db` | 3 986 | 3 978 | 8 |
| `refactoring_db` | 2 043 | 1 761 | 282 |
| `mixed` | 6 029 | 5 739 | 290 |

`mixed` je presne zjednotením testing a refactoring korpusu. Neobsahuje literatúru. Single RAG a MultiRAG teda porovnávajú ten istý unikátny obsah, iba s inou organizáciou kolekcií.

V retrieval V3 sa embeduje iba vstupná strana príkladu a typ úlohy; referenčný output ostáva v dokumente ako evidencia poskytnutá modelu po retrievale. Toto zlepšenie zabraňuje tomu, aby referenčný output umelo ovplyvňoval similarity score.

### 9.4 Proveniencia a naming problém

`configs/datasets/manifests/refactoring_retrieval.yaml` sa volá `ml4refactoring_retrieval`, ale `source_path` ukazuje na `data/processed/refactoring/train.jsonl`, ktorý obsahuje ML4Refactoring aj MaRV. To isté platí pre benchmark manifest. Odporúčaný názov je napr. `refactoring_mix_retrieval_v1` a manifest má explicitne obsahovať obidva upstream zdroje a ich hashe.

## 10. Handcrafted smoke dataset

`handcrafted_smoke_v1` je náš vlastný, ručne vytvorený dataset s 24 prípadmi:

- 12 testing,
- 12 refactoring,
- pre každú úlohu 4 easy, 4 medium a 4 tricky.

Jeho účel je:

- overenie, že pipeline funguje end-to-end,
- regresná kontrola Direct/RAG/MultiRAG,
- kontrola promptov a evaluátorov,
- deterministické malé piloty.

Nie je určený na:

- fine-tuning,
- retrieval/indexovanie,
- odhad všeobecnej výkonnosti modelu.

Testing prípady obsahujú Java vstup, focal method, požiadavky a očakávané scenáre. Refactoring prípady majú navyše behavior test a ilustračný reference code. Reference code nie je exact-match oracle; platné je každé kompilovateľné, behavior-preserving riešenie spĺňajúce kontrolované invariants.

Dataset má SHA-256 fingerprinty inputu, normalizovaného inputu a focal method. Aktuálny leakage report deklaruje nulový overlap so všetkými tromi produkčnými kolekciami. Report však obsahuje staršie dataset manifest IDs a bol vytvorený pred V3 indexom. Hoci podkladové počty sú rovnaké, po každom novom indexe treba report obnoviť a pripnúť na aktuálne manifest ID.

## 11. Externé benchmarky

### 11.1 TestBench

[TestBench](https://arxiv.org/abs/2409.17561) obsahuje 108 Java programov z 9 reálnych projektov a tri kontextové režimy. Pôvodná evaluácia sleduje syntax, kompiláciu, správnosť testu, coverage a defect detection.

Náš adaptér vie načítať `source`, `simple` alebo `full` context a vytvoriť kompletnú JUnit Jupiter test-class úlohu. Config očakáva 108 prípadov a Maven vykonanie.

**Aktuálny stav:** priečinok `benchmarks/TestBench-main` v pracovnom priestore chýba. TestBench teda nie je súčasťou aktuálneho lokálneho dátového behu a nesmie byť reportovaný ako dokončená evaluácia.

### 11.2 SWE-Refactor

[SWE-Refactor](https://arxiv.org/abs/2602.03712) deklaruje 1 099 behavior-preserving refaktoringov z 18 Java projektov, z toho 922 atomic a 177 compound. Prípady boli podľa autorov overené kompiláciou, testami a refactoring detection.

Náš adaptér načítava pure refactoring prípady, before code, reference after code, typ, project/commit/file metadata a compile/test metadata.

**Aktuálny stav:** priečinok `benchmarks/swe-refactor/SWE-Refactor` chýba. Benchmark je pripravený v kóde a configu, ale nie je lokálne materializovaný ani dokončene vyhodnotený.

### 11.3 Prečo ich potrebujeme

Interné test splity pochádzajú z rovnakých zdrojových rodín ako tréning. TestBench a SWE-Refactor môžu poskytnúť nezávislejšiu, executable a realistickejšiu evaluáciu. Pred použitím treba aj tak vykonať project/commit/code-fingerprint audit voči tréningovým a retrieval dátam.

## 12. Dáta, ktoré sa aktuálne nepoužívajú

- `data/external` neobsahuje schválené externé dokumenty.
- Literatúrna RAG kolekcia sa nestavia; produkčný report explicitne uvádza `not_indexed`.
- Ontológia, GraphRAG a projektový kontext nie sú súčasťou aktuálneho dátového baseline.
- Validation a test JSONL sa neindexujú.
- Smoke prípady sa neindexujú ani netrénujú.
- `data/samples/*.json` sú iba dokumentačné príklady schémy.
- ML4Refactoring štrukturálne metriky a projektový spreadsheet náš generatívny pipeline nepoužíva.

## 13. Reprodukovateľnosť a integrita

### 13.1 Overené SHA-256 processed súborov

| Súbor | SHA-256 |
|---|---|
| `testing/train.jsonl` | `6a2ebc5d0dbbfd2f2dbc4b653a45ec9fdc4f9ae836da3a64f1f44e8d5f09b401` |
| `testing/val.jsonl` | `8e48b96d25041811cc7fb96e1f84401b816787640501840f9d1e38a8ffff7e1f` |
| `testing/test.jsonl` | `18dd06494f8ebc6fc26b6f330930637446d4f78aac2e10b36b581ade6a91be68` |
| `refactoring_ml4ref/train.jsonl` | `453132a5777cf08f38d6a09b511e2c1167cb4a3a78e8c3723c608534c1f0ca19` |
| `refactoring_ml4ref/val.jsonl` | `46923c1e0db6d9c599ae0ca2d2211419061f738a4a766e059d430cb29c47935c` |
| `refactoring_ml4ref/test.jsonl` | `14c506264d45a9f1822cb8db20889801e29f784491c2efd6a2947dc872adc848` |
| `refactoring_marv/train.jsonl` | `410657fed2781a02ca823ba068b12fadb39ad0b0147f1e15576fffb8a4e79b43` |
| `refactoring_marv/val.jsonl` | `c76df648df4ce509b1a68991405e79ac457d67a8b7debe461efced6cdb70f596` |
| `refactoring_marv/test.jsonl` | `64a3053f02ee788aeda3d3b183dec5e8ae3037e2ff29f4631d43e9e36d52a83d` |
| `refactoring/train.jsonl` | `f70853aa924a9d212d5701f31af14f34b8e2f2232b61700a8c2590a13a64aabb` |
| `refactoring/val.jsonl` | `11af7a848ecd3e8c4c3bafa174a43568838eff663a2bf9b1f0385dfeecdd1642` |
| `refactoring/test.jsonl` | `86d064ef7919ce9a94382ad1e352e5e8b62c097a0245228a3e7f51fabec8d31e` |
| `combined/train.jsonl` | `3aa28a139a03b6785d021d7699bb3f0ad02f8b029e0b227c71cb41738d1cc875` |
| `combined/val.jsonl` | `20f684f8070104b2da44385a3bc4f2318e68b8e78e7bdfc65405a89f4aad15ad` |
| `combined/test.jsonl` | `9768be380a7e57d5548e70f468987d35ef7bdb07f93c29fba5d8cea130a59ff1` |

Testing a finálny refactoring train/test hash sa zhodujú s existujúcimi dataset manifestmi.

### 13.2 Raw verzie

- Methods2Test lokálny Git checkout: commit `574b84b633eaaa0efb83afd80b29878a9537ed90`; rozbalené `corpus/json/*` sú v tomto checkoute untracked, preto samotný Git commit nestačí na identifikáciu raw korpusu.
- ML4Refactoring: Zenodo record `10.5281/zenodo.3547639`; lokálny 40 GB archív nemá v projektovom manifeste overený checksum.
- MaRV: Zenodo record `10.5281/zenodo.14450098`; lokálny raw SHA-256 je uvedený vyššie a obsahovo zodpovedá 698-record verzii, nie publikovanému 693-record výberu.

### 13.3 Licencie a proveniencia

Methods2Test checkout obsahuje MIT licenciu a paper uvádza, že zdrojové projekty mali licencie umožňujúce redistribúciu. Pri ML4Refactoring a MaRV však naše dataset manifesty neuchovávajú licenciu, DOI verziu, dátum stiahnutia ani upstream checksum ako povinné polia.

Pred odovzdaním práce treba vytvoriť dataset registry s minimálne:

- názvom a presnou verziou zdroja,
- DOI/URL,
- autorom a citáciou,
- licenciou a podmienkami redistribúcie,
- dátumom získania,
- upstream checksumom,
- lokálnym raw checksumom,
- processing code commitom,
- processing parametrami a seedom,
- checksumami všetkých výsledných splitov.

## 14. Riziká pre interpretáciu výsledkov

| Riziko | Dopad na výsledok | Závažnosť |
|---|---|---:|
| ML4Ref exact páry v train aj test | model môže „uspieť“ memorovaním | kritická |
| projekt/commit overlap ML4Ref | nadhodnotená generalizácia | kritická |
| MaRV nefiltruje negatívny konsenzus | chybné supervision labels | kritická |
| staré materializované splity vs nový kód | nemožno presne reprodukovať dáta iba z aktuálneho kódu | vysoká |
| sorted-first sampling | selection bias a slabá reprezentatívnosť | vysoká |
| 33 % ML4Ref nad 2 048 tokenov | strata inputu/outputu, zmena reálnej úlohy | vysoká |
| `unknown` typ pri 15,82 % ML4Ref | slabší alebo chybný instruction signal | vysoká |
| shared 50:50 iba podľa riadkov | refactoring dominuje tokenom | vysoká |
| shared má viac dát než specialisti | size confound pri porovnaní | vysoká |
| smoke je iba 24 ručných prípadov | nemožno z neho vyvodzovať všeobecnú kvalitu | stredná |
| externé benchmarky chýbajú | chýba nezávislá finálna evaluácia | vysoká |
| neúplná licencia/verzia v manifestoch | slabší akademický a právny audit trail | stredná až vysoká |
| refactoring manifest nesprávne pomenúva mix | nepresná proveniencia v reporte | stredná |

## 15. Odporúčaný opravný plán pred finálnymi experimentmi

### Priorita P0 — pred akýmkoľvek finálnym tvrdením

1. **Zmraziť súčasné výsledky ako exploratívne.** Nemiešať ich s výsledkami po oprave dát.
2. **Regenerovať ML4Refactoring od začiatku:**
   - najprv normalizovať a deduplikovať exact/normalized before-after páry,
   - opraviť kompletný zoznam typov a zakázať `unknown`, ak nie je vedomou triedou,
   - splitovať po project alebo minimálne repository+commit skupine,
   - až potom vyberať cieľové počty,
   - overiť nulový pair, input, project a commit overlap.
3. **Definovať MaRV quality policy.** Odporúčaný primárny tréningový variant používa iba `(1,1)` pozitívny konsenzus. `(0,0)` môže slúžiť ako negatívna trieda pre inú úlohu; konflikty a one-vote prípady treba oddeliť alebo použiť iba v ablation.
4. **Regenerovať MaRV split repository/commit-aware spôsobom** a overiť nulový overlap.
5. **Regenerovať Methods2Test subset reprezentatívne:** náhodne alebo stratifikovane vzorkovať projekty v rámci oficiálnych splitov, s explicitným seedom. Uchovať project/repository metadata ako samostatné polia.
6. **Po zmene dát pretrénovať všetky adaptéry.** Staré adaptéry ostávajú viazané na staré split hashe.

### Priorita P1 — férovosť tréningu

7. Rozhodnúť, či ML4Ref input/output má byť celý súbor, zmenená metóda alebo štruktúrovaný diff. Preferovať úroveň, ktorá sa zmestí do kontextu a zodpovedá evaluačnej úlohe.
8. Pridať tokenizer-aware filter/report pred tréningom. Každý dataset build má uviesť počet skrátených promptov a outputov.
9. Pre shared vs specialist porovnanie zaviesť aspoň jednu kontrolu:
   - rovnaký počet záznamov,
   - rovnaký počet tréningových tokenov,
   - rovnaký počet optimizer krokov,
   - size ablation.
10. Rozhodnúť, či MaRV patrí aj do shared modelu. Ak nie, explicitne vysvetliť, že shared refactoring polovica reprezentuje iba ML4Refactoring.
11. Zjednotiť jazyk instruction promptov alebo urobiť jazykovú ablation.

### Priorita P2 — finálna evaluácia a audit trail

12. Stiahnuť a verziovať TestBench a SWE-Refactor, potom vykonať cross-source leakage audit.
13. Použiť smoke iba na pipeline correctness, nie ako hlavný dôkaz modelovej kvality.
14. Obnoviť smoke leakage report pre presný V3 manifest alebo pre finálne zmrazený retrieval baseline.
15. Premenovať refactoring manifesty tak, aby reprezentovali ML4Refactoring+MaRV mix.
16. Vygenerovať jeden strojovo čitateľný `dataset_registry.json` a jeden `dataset_build_report.json` pre každú finálnu verziu.
17. Do práce reportovať nielen počet riadkov, ale aj:
   - počet unikátnych projektov/commitov/párov,
   - distribúciu typov,
   - dĺžky a truncation,
   - počet vyradených záznamov podľa dôvodu,
   - hash každého splitu,
   - presnú rolu: train, validation, internal test, retrieval alebo external benchmark.

## 16. Odporúčaná formulácia do diplomovej práce

Nasledujúci text je možné po regenerácii čísel použiť ako základ metodickej časti:

> Experiment používa tri externé dátové zdroje. Methods2Test poskytuje páry Java focal methods a developer-written JUnit test cases. ML4Refactoring poskytuje historické before/after reprezentácie refaktoringov z reálnych projektov a v tejto práci je repurposovaný na generatívnu code-to-code úlohu. MaRV dopĺňa refaktoringovú doménu o manuálne hodnotené príklady štyroch typov refaktoringu. Všetky zdroje sú transformované do jednotnej instruction-tuning schémy s poliami instruction, input, output, domain a source. Splity sú vytvárané na skupinovej úrovni tak, aby sa projekty alebo commity neopakovali medzi tréningom a finálnou evaluáciou; exact a normalizované code fingerprinty sa kontrolujú samostatne. Retrieval index používa výhradne leakage-safe časť train splitu. Validation, test, handcrafted smoke a externé benchmarkové prípady sa nikdy neindexujú.

Túto formuláciu nemožno bez úpravy použiť pre aktuálne materializované ML4Refactoring/MaRV splity, pretože audit preukázal cross-split overlap a nesynchronizáciu s novšou implementáciou.

## 17. Jednovetové odpovede pre vedúceho práce

**Aké datasety používame?**  
Methods2Test pre generovanie JUnit testov, ML4Refactoring a MaRV pre refaktoring, vlastný 24-prípadový smoke dataset pre pipeline kontrolu; TestBench a SWE-Refactor sú pripravené ako budúce nezávislé benchmarky.

**Čo z nich berieme?**  
Z Methods2Test focal method a test case, z ML4Refactoring before/after Java súbory a project/commit/type metadata, z MaRV before/after diffy, typy, commit metadata a manuálne hlasy.

**Čo pridávame my?**  
Slovenské inštrukcie, jednotné polia `domain` a `source`, dĺžkové a obsahové filtre, splity, mixy, seedované premiešanie, manifesty, hashe, leakage filtering, embedding text a vlastné smoke prípady.

**Prečo to robíme?**  
Aby sa heterogénne zdroje dali použiť v rovnakom fine-tuning, RAG a evaluation pipeline a aby bolo možné porovnať testing, refactoring a shared model za kontrolovaných podmienok.

**Je aktuálny dataset finálny?**  
Nie úplne: je vhodný na vývoj a exploratívne behy, ale pred finálnym reportovaním treba odstrániť ML4Ref cross-split duplicity, zaviesť MaRV vote policy, opraviť sampling a truncation a následne experimenty zopakovať.

## 18. Primárne zdroje

- Tufano et al.: [Methods2Test: A dataset of focal methods mapped to test cases](https://arxiv.org/abs/2203.12776)
- Microsoft: [Methods2Test repository](https://github.com/microsoft/methods2test)
- Aniche et al.: [The Effectiveness of Supervised Machine Learning Algorithms in Predicting Software Refactoring](https://arxiv.org/abs/2001.03338)
- Aniche et al.: [ML 4 Refactoring dataset, Zenodo 3547639](https://zenodo.org/records/3547639)
- Nunes, Sharma, Figueiredo: [MaRV: A Manually Validated Refactoring Dataset](https://labsoft-ufmg.github.io/publications/2025/forge2025preprint.pdf)
- Nunes et al.: [MaRV Scripts and Dataset, Zenodo 14450098](https://zenodo.org/records/14450098)
- Zhang et al.: [TestBench: Evaluating Class-Level Test Case Generation Capability of Large Language Models](https://arxiv.org/abs/2409.17561)
- Xu et al.: [SWE-Refactor: A Repository-Level Benchmark for Real-World LLM-Based Code Refactoring](https://arxiv.org/abs/2602.03712)

## 19. Lokálne auditované podklady

- `src/llm_ontology/datasets/` — preprocessing, čistenie a splitovanie,
- `scripts/datasets/` — spustiteľné dataset workflow,
- `data/raw/` — lokálne raw zdroje,
- `data/processed/` — auditované JSONL splity,
- `configs/datasets/manifests/` — roly, počty a hashe,
- `artifacts/indexes/production_corpus/` — leakage-safe retrieval deriváty,
- `artifacts/split_audits/` — group a fingerprint audity,
- `artifacts/retrieval/indexes/` — produkčné index reporty,
- `data/chroma/ollama_bge_m3_v3/manifests/` — lokálne V3 collection manifesty,
- `thesis_materials/handcrafted_skills/smoke_cases/` (dáta a opis) — vlastný smoke dataset,
- `docs/datasets/raw_record_examples.md` — úplný raw príklad z Methods2Test,
  ML4Refactoring a MaRV,
- `thesis_materials/handcrafted_skills/smoke_cases/handcrafted_smoke_all_cases.md` — všetkých 24 smoke záznamov
  vrátane kompletných Java fixtures a behavior testov,
- `configs/finetuning/` — mapovanie datasetov na B1/B2 modely,
- `configs/evaluation/` a `configs/benchmarks/` — interné a externé evaluačné vstupy.
