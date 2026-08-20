# Handcrafted smoke dataset

`handcrafted_smoke_v1` je malý, ručne kontrolovateľný referenčný dataset pre
Java test generation a refactoring. Slúži na smoke/regresné overenie,
debugovanie Direct/RAG/MultiRAG, kontrolu promptov a evaluátorov a malé pilotné
experimenty. Nie je tréningový ani retrieval dataset a nesmie byť vložený do
žiadnej Chroma kolekcie.

Manifest v `data/smoke/manifest.yaml` preto používa
`usage_role: smoke_evaluation` a `allowed_for_indexing: false`. Rovnaký zákaz
prenáša loader do metadata každého `BenchmarkCase`; štandardná manifestová
ochrana `require_indexable()` dataset odmietne.

## Rozsah

Dataset obsahuje presne 24 prípadov: 12 pre `testing` a 12 pre `refactoring`.
Každá úloha má štyri `easy`, štyri `medium` a štyri `tricky` prípady.

| ID | Zameranie |
|---|---|
| `testing_easy_001` | sčítanie celých čísel naprieč znamienkami |
| `testing_easy_002` | parita kladných, záporných a nulových hodnôt |
| `testing_easy_003` | skladanie a orezanie celého mena |
| `testing_easy_004` | maximum vrátane zhody vstupov |
| `testing_medium_001` | celočíselné delenie, znamienka a delenie nulou |
| `testing_medium_002` | inkluzívny rozsah a neplatné hranice |
| `testing_medium_003` | prvá zhoda, prázdny zoznam a `null` |
| `testing_medium_004` | normalizácia `null`, whitespace a veľkosti písmen |
| `testing_tricky_001` | stavový počítadlový objekt a hranice |
| `testing_tricky_002` | vetvený shipping fee a validačné výnimky |
| `testing_tricky_003` | výrez textu, indexy a rozdielne výnimky |
| `testing_tricky_004` | akumulovaný stav a immutable view |
| `refactoring_easy_001` | Inline Variable |
| `refactoring_easy_002` | Remove Dead Code |
| `refactoring_easy_003` | Simplify Boolean Expression |
| `refactoring_easy_004` | Rename Variable |
| `refactoring_medium_001` | Extract Method pri percentuálnej zľave |
| `refactoring_medium_002` | nahradenie vnorených podmienok guard clause |
| `refactoring_medium_003` | konsolidácia duplicitného fragmentu vetiev |
| `refactoring_medium_004` | extrakcia spoločnej aplikácie dane |
| `refactoring_tricky_001` | extrakcia vetvy risk klasifikácie |
| `refactoring_tricky_002` | sploštenie booking eligibility podmienok |
| `refactoring_tricky_003` | dekompozícia zľavy a regionálnej dane |
| `refactoring_tricky_004` | extrakcia notification priority policy |

Prípady nepoužívajú sieť, databázu, concurrency ani časovo závislé správanie.

## Súbory a schéma

```text
data/smoke/
  manifest.yaml
  leakage_report.json
  harness/SmokeTestLauncher.java
  testing/
    cases.jsonl
    fixtures/<case_id>/Input.java
  refactoring/
    cases.jsonl
    fixtures/<case_id>/Input.java
    fixtures/<case_id>/BehaviorTest.java
```

Každý JSONL záznam validuje diskriminovaný Pydantic model `SmokeCase`:

- spoločné polia: `id`, `task`, `difficulty`, `title`, `expected_process`,
  `validation_rules`, `tags`, `notes` a tri fingerprinty;
- `input`: typovaný testing/refactoring vstup s Java zdrojom, focal metódou,
  požiadavkami a cestami k fixtures;
- `expected_output`: pre testing JUnit framework, focal call, minimálny počet
  testov, scenáre a výnimky; pre refactoring typy refaktoringu, behavior/API
  invariants, štrukturálne očakávania a voliteľný ilustračný `reference_code`.

`reference_code` nie je exact-match oracle. Refactoring sa má hodnotiť
kompiláciou, preddefinovanými behavior testami, zachovaním API a iba primerane
úzkymi štrukturálnymi kontrolami. Iné ekvivalentné riešenie je platné.

`expected_process` je krátky evaluator-facing opis. Loader ho nikdy nevkladá
do promptu a nesmie sa používať ako požiadavka na chain-of-thought. Behavior
testy, validation rules a expected output sa takisto neposielajú modelu.

Hash polia majú rozdielny účel:

- `input_code_hash`: SHA-256 presných UTF-8 bajtov `source_code`,
- `normalized_input_code_hash`: lexikálne normalizovaný Java fingerprint,
- `focal_method_hash`: lexikálne normalizovaný fingerprint focal metódy.

Manifest verzia `1.0` pinne oba JSONL súbory jedným deterministickým content
hashom, schema verziu a počet 24 prípadov.

## Načítanie a validácia

Dataset je registrovaný v existujúcom benchmark registry pod
`handcrafted_smoke_v1` a aliasom `smoke`. Loader vracia štandardné
`BenchmarkCase`, takže nepotrebuje samostatný experiment runner.

Kompletná kontrola z koreňa repozitára:

```bash
source .venv_wsl/bin/activate
python scripts/benchmarks/validate_smoke_dataset.py \
  --audit-leakage --write-leakage-report
```

Validátor kontroluje schému, rozdelenie, IDs, hashe, súlad JSONL a fixtures,
manifest a validation rules. Následne:

1. skompiluje všetkých 24 `Input.java`,
2. skompiluje a spustí 12 behavior fixtures nad pôvodným vstupom,
3. zopakuje rovnaké behavior testy nad 12 referenčnými refaktoringmi,
4. porovná fingerprinty s aktuálnymi `testing_db`, `refactoring_db` a `mixed`.

Používa dostupný JDK a JUnit 5 artefakty z lokálneho Maven cache. Premenné
`SMOKE_JAVAC`, `SMOKE_JAVA` a `SMOKE_JUNIT_CLASSPATH` umožňujú explicitne
určiť toolchain. Vo WSL vie validátor použiť aj hostiteľský JDK iba na offline
kompilačnú kontrolu fixtures; finálne modelové experimenty naďalej patria
výhradne do WSL runtime.

Aktuálny audit je uložený v `data/smoke/leakage_report.json`: všetky tri
produkčné kolekcie majú nulový počet overlapov. Report porovnáva normalizovaný
input, focal metódu, celý normalizovaný dokument a štruktúrovanú identitu, ak
je dostupná.

## Pridanie alebo zmena prípadu

1. Zvoľ unikátne ID podľa `<task>_<difficulty>_<NNN>` a zachovaj deklarovanú
   distribúciu alebo vedome vytvor novú dataset verziu.
2. Pridaj ručne napísaný JSONL záznam a zodpovedajúci `Input.java`.
3. Pri refactoringu pridaj behavior test, ktorý prejde pred aj po zmene; môžeš
   pridať ilustračný reference code, nikdy však exact-match požiadavku.
4. Obnov hashe cez `--refresh-hashes`, následne aktualizuj content hash
   manifestu. Zmena obsahu po vydaní spravidla znamená novú verziu datasetu.
5. Spusť validátor s `--audit-leakage` a celý `pytest` suite. Konfliktný prípad
   uprav alebo nahraď; overlap sa nesmie potichu akceptovať.
6. Aktualizuj a commitni leakage report spolu s datasetom.

Smoke dáta sa nikdy nepridávajú do produkčného index buildera, retrieval
manifestov ani tréningových splitov.
