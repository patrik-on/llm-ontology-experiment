# Report k diplomovej práci: výsledky `baseline_v2`

## Zhrnutie

Experiment `baseline_v2` bol 21. augusta 2026 úspešne dokončený v canonical WSL
runtime. Obsahoval 24 smoke prípadov v troch režimoch, teda spolu 72 behov. Preflight,
kontrola prompt fairness aj baseline fingerprint prešli. Všetkých 72 behov skončilo
validným štruktúrovaným JSON výstupom na prvý pokus a runner nezaznamenal žiadne technické
zlyhanie.

Tento technický výsledok však nemožno interpretovať ako 72 správnych Java riešení. Proxy
metriky ukazujú úplnú remízu pri generovaní testov a malú výhodu Direct pri refaktoringu.
Dodatočný syntaktický audit navyše odhalil, že iba 16 z 36 vygenerovaných testovacích
výstupov prešlo Java parserom. Hlavný záver preto je:

> V2 odstránila runtime orezávanie promptov a katastrofický pokles RAG pozorovaný vo V1,
> ale nepreukázala zlepšenie kvality oproti Direct. Aktuálne testing proxy skóre je
> saturované a bez kompilácie výrazne nadhodnocuje kvalitu generovaných testov. MultiRAG
> navyše stále nepoužíva skutočne odlišný druhý znalostný zdroj.

## Reprodukovateľnosť behu

| Parameter | Hodnota |
|---|---|
| Baseline | `baseline_v2` |
| Fingerprint | `f581a5612e9e0858992943913b85860e8a1329b384772942bd376fad97e3e9c9` |
| Matica | 24 prípadov × 3 režimy = 72 behov |
| Úspešné/technicky zlyhané | 72/0 |
| Prompt fairness | PASS |
| Runtime | WSL2, Linux, Python 3.13.11 |
| Generačný model | `qwen2.5-coder:7b` |
| Embedding model | `bge-m3`, 1024 rozmerov |
| Ollama context window | 32 768 tokenov |
| Retrieval | `top_k=3`, `per_collection_top_k=3`, RRF `k=60` |
| Limit jedného evidence dokumentu | 768 tokenizer tokenov |
| Wall-clock čas | približne 18,74 minúty |

Modelové digesty, identity troch Chroma kolekcií a presná efektívna konfigurácia sú uložené
v [environment.json](artifacts/experiments/smoke/baseline_v2/environment.json) a
[effective_config.yaml](artifacts/experiments/smoke/baseline_v2/effective_config.yaml).
Kompletnou primárnou evidenciou je [runs.jsonl](artifacts/experiments/smoke/baseline_v2/runs.jsonl).

## Hlavné proxy výsledky V2

| Úloha | Direct | Single RAG | MultiRAG | Single − Direct | Multi − Direct |
|---|---:|---:|---:|---:|---:|
| Generovanie testov | 8,5000 | 8,5000 | 8,5000 | 0,0000 | 0,0000 |
| Refaktoring | **8,4778** | 8,3919 | 8,3899 | −0,0859 | −0,0879 |

Pri testingu dosiahli všetky režimy 100 % výskyt `@Test`, assertion a volania cieľovej
metódy, pričom trivial-smell proxy bola 0 %. Takáto úplná zhoda však nevznikla preto, že by
model generoval rovnaké riešenia. Direct výstup sa nezhodoval so Single ani Multi výstupom
ani v jednom z 12 testing prípadov. Metrika iba nedokázala rozlíšiť ich kvalitu.

Pri refaktoringu zostal Direct mierne najlepší:

- Single RAG: 2 výhry, 2 prehry a 8 remíz voči Direct;
- MultiRAG: 1 výhra, 2 prehry a 9 remíz voči Direct;
- Direct dosiahol presnú zhodu s ilustračným referenčným riešením v 5 z 12 prípadov,
  Single aj Multi v 4 z 12 prípadov.

Rozdiel je koncentrovaný najmä v `refactoring_tricky_002`. Direct vytvoril presne referenčný
kombinovaný guard a dostal 9,0858. Oba RAG režimy vytvorili tri samostatné guard clauses a
dostali 8,2877. Alternatíva RAG vyzerá behaviorálne rozumne, ale bez spustenia pripraveného
`BehaviorTest.java` nemožno rozdiel −0,7982 interpretovať ako reálne zhoršenie správania.
Naopak, pri `refactoring_medium_002` sa výstupy líšia prakticky iba prázdnymi riadkami, no
proxy code-health skóre sa zmenilo o celý bod. To ukazuje citlivosť heuristiky na formátovanie.

Podrobnosti sú v [summary.json](artifacts/experiments/smoke/baseline_v2/summary.json) a
[case_comparison.csv](artifacts/experiments/smoke/baseline_v2/case_comparison.csv).

## Porovnanie V1 a V2

| Úloha | Režim | V1 | V2 | Zmena V2 − V1 |
|---|---|---:|---:|---:|
| Testing | Direct | 8,5000 | 8,5000 | 0,0000 |
| Testing | Single RAG | 8,5000 | 8,5000 | 0,0000 |
| Testing | MultiRAG | 7,7500 | 8,5000 | **+0,7500** |
| Refaktoring | Direct | 8,4100 | 8,4778 | +0,0678 |
| Refaktoring | Single RAG | 8,1184 | 8,3919 | **+0,2735** |
| Refaktoring | MultiRAG | 6,4396 | 8,3899 | **+1,9503** |

V2 teda odstránila veľký prepad MultiRAG a výrazne zmenšila rozdiel medzi Direct a RAG.
Priemerný refactoringový čas MultiRAG klesol približne z 34,54 s vo V1 na 14,80 s vo V2.
Tieto zlepšenia nemožno pripísať jednej izolovanej zmene, pretože V2 súčasne zaviedla
`num_ctx=32768`, task filter, menšie `top_k`, per-document limit a párové skracovanie.
Ide o výsledok celého bezpečnostného balíka V2, nie o samostatnú abláciu jeho častí.

## Retrieval a tokenový rozpočet

| Režim | Priemer retrieved docs | Priemer prompt docs | Priemer retrieval tokenov | Skrátené dokumenty | Max. finálny prompt | Runtime truncation |
|---|---:|---:|---:|---:|---:|---:|
| Direct | 0,000 | 0,000 | 0,00 | 0 | 398 | 0/24 |
| Single RAG | 3,000 | 2,958 | 1 201,96 | 23 | 2 929 | 0/24 |
| MultiRAG | 2,625 | 2,625 | 1 130,04 | 22 | 2 927 | 0/24 |

Najdôležitejším technickým výsledkom je, že ani jeden zo 72 behov nemá podozrenie na
runtime truncation. Najdlhší finálny prompt mal 2 929 tokenov; spolu s rezervou 4 096
výstupných tokenov a bezpečnostnou rezervou bol výrazne pod 32 768-tokenovým limitom.
Problém V1, kde `prompt_eval_count` končil na 4 096, sa už neobjavil.

Per-document limit zasiahol 45 refactoringových evidence dokumentov. Všetkých 45 bolo v
run záznamoch označených ako pair-aware truncation, teda skracovanie zachovalo sekciu
pôvodného aj výsledného kódu. Nebol vyradený ani jeden dokument. Testing evidence boli
kratšie a limit 768 tokenov neprekročili.

Priemerná retrieval latencia bola približne 2,05 s pre Single RAG a 1,99 s pre MultiRAG.
Nižšia MultiRAG latencia neznamená efektívnejší plnohodnotný multi-source retrieval: obe
kolekcie sa dopytujú paralelne a opačná tasková kolekcia po aplikovaní filtra neposkytuje
kandidátov.

Kompletné tokenové a retrieval údaje sú v
[retrieval_analysis.json](artifacts/experiments/smoke/baseline_v2/retrieval_analysis.json).

## Single RAG verzus MultiRAG

Task filter fungoval správne a zabránil miešaniu testing a refactoring príkladov. Zároveň
však odhalil, že súčasný MultiRAG nie je skutočne multi-source:

- `mixed` po task filtri obsahuje ten istý taskový korpus ako zodpovedajúca špecializovaná
  kolekcia;
- opačná špecializovaná kolekcia je po filtri prázdna;
- MultiRAG preto nemá literatúru, ontológiu ani projektový kontext ako druhý odlišný zdroj.

V plnom behu mali Single a Multi presne rovnakú množinu prompt dokumentov v 14 z 24
prípadov. V 20 z 24 prípadov bola Multi množina podmnožinou Single množiny a priemerný
Jaccardov prekryv bol 0,7861. Rozdiely vznikali najmä RRF deduplikáciou a mierne odlišným
výsledkom približného vyhľadávania v `mixed` a špecializovanom indexe. Single a Multi
vygenerovali presne rovnaký kód v 17 z 24 prípadov.

Výsledok MultiRAG preto nemožno použiť ako dôkaz prínosu kombinácie viacerých typov
znalostí. Je to skôr kontrola dvoch indexových ciest nad takmer rovnakým zdrojovým korpusom.

## Dodatočný syntaktický audit výstupov

Automatický runner označuje `success`, keď Ollama vráti validný JSON podľa Pydantic schémy.
Nekompiluje kód. Preto bol nad všetkými 72 predikciami dodatočne spustený read-only
Tree-sitter Java syntax audit.

| Úloha | Direct | Single RAG | MultiRAG | Spolu |
|---|---:|---:|---:|---:|
| Testing: syntakticky prijaté | 8/12 | 4/12 | 4/12 | **16/36** |
| Refaktoring: syntakticky prijaté | 12/12 | 12/12 | 12/12 | **36/36** |

Pri testingu parser odmietol 20 výstupov. Typické chyby boli náhodné znaky medzi `@Test`
a deklaráciou metódy (`d void`, `g void`, `t public void`) alebo nadbytočná zátvorka v
assertion. Napríklad `testing_easy_001` je v Direct syntakticky korektný, ale oba RAG
výstupy obsahujú tri deklarácie začínajúce `d void`. Napriek tomu dostali všetky tri režimy
rovnaké proxy skóre 8,0.

Tree-sitter kontroluje iba syntax. Nekontroluje dostupnosť importov, typov, správnosť
assertion ani reálne spustenie testov. Skutočná miera kompilácie preto môže byť ešte nižšia
ako 16/36. Refactoringových 36/36 syntakticky prijatých výstupov zase neznamená, že všetky
zachovávajú správanie.

## Obmedzenia experimentu

1. Testing proxy metrika je saturovaná. Všetkých 36 výstupov dostalo iba skóre 8 alebo 9,
   hoci 20 z nich neprešlo ani syntaktickým parserom.
2. Smoke runner zatiaľ nevykonáva `javac`, JUnit ani refactoringové behavior fixtures nad
   vygenerovanými predikciami.
3. Refactoringové heuristiky sú citlivé na formátovanie a podobnosť s jedným ilustračným
   referenčným riešením. Alternatívne správny refaktoring môže dostať nižšie skóre.
4. Každá bunka obsahuje iba 12 prípadov a jeden deterministický beh so seed 42. Nie je
   dostupný odhad variability ani štatistickej významnosti.
5. V2 zmenila viac parametrov naraz, takže výsledok neizoluje účinok task filtra, `top_k`,
   context window ani skracovania.
6. MultiRAG nemá nezávislý druhý znalostný zdroj.
7. Baseline fingerprint zachytáva konfiguračný kontrakt, ale nie verziu implementácie
   pair-aware compaction. Pre finálne experimenty treba uložiť aj Git commit a verziu
   compaction stratégie.

## Odporúčané pokračovanie

Najvyššiu prioritu má executable evaluation, nie ďalšie ladenie proxy skóre:

1. Pri testingu skompilovať vstupnú triedu spolu s vygenerovaným JUnit testom a test reálne
   spustiť. Do výsledku zapísať syntax, compile, execution a scenario coverage samostatne.
2. Pri refaktoringu nahradiť vstup vygenerovaným kódom, skompilovať ho s existujúcim
   `BehaviorTest.java` a behavior test spustiť.
3. Rozšíriť structured-output validáciu o Java syntax alebo kompiláciu a neplatný kód
   automaticky poslať do jedného kontrolovaného repair retry.
4. Doplniť MultiRAG o reálne odlišný zdroj: `literature_db`, `ontology_concepts` alebo
   projektový kontext. Až potom opakovať porovnanie Single verzus Multi.
5. Následne vykonať abláciu retrievalu: input-only retrieval key verzus paired payload,
   reranker a špecializovaná kolekcia verzus `mixed`.

## Formulácia vhodná do diplomovej práce

> Druhá verzia experimentálneho pipeline odstránila pozorované orezávanie kontextu a
> stabilizovala RAG aj MultiRAG na úroveň blízku priamemu generovaniu. Pri refaktoringu
> však Direct zostal v priemere mierne najlepší a pri generovaní testov proxy metriky
> nerozlíšili režimy. Dodatočná syntaktická analýza ukázala, že veľká časť testovacích
> výstupov nebola syntakticky validná, čo potvrdzuje potrebu kompilácie a behaviorálneho
> vykonávania ako primárnej evaluačnej vrstvy. Súčasná MultiRAG konfigurácia navyše
> kombinuje indexové cesty nad rovnakým taskovým korpusom, preto zatiaľ nehodnotí prínos
> heterogénnych znalostných zdrojov.
