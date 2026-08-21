# Priebežný report k diplomovej práci: `baseline_v1` a návrh V2

## Výsledok `baseline_v1`

Experiment obsahoval 24 smoke prípadov × 3 režimy, spolu 72 behov. Všetkých 72 behov
prešlo technicky úspešne a prompt-fairness kontrola bola úspešná. Celý beh trval približne
23,9 minúty. Technický úspech však znamená iba úspešné volanie Ollamy a validný výstupný
JSON, nie automaticky kompilovateľný alebo behaviorálne správny Java kód.

| Úloha | Direct | Single RAG | MultiRAG |
|---|---:|---:|---:|
| Generovanie testov | 8,50 | 8,50 | 7,75 |
| Refaktoring | 8,41 | 8,12 | 6,44 |

Voči Direct bol Single RAG pri testovaní bez zmeny a pri refaktoringu horší o 0,29 bodu.
MultiRAG bol horší o 0,75 bodu pri testovaní a o 1,97 bodu pri refaktoringu. Pri
refaktoringu MultiRAG nevyhral ani jeden prípad, štyrikrát remizoval a osemkrát prehral.
Najväčší pokles nastal pri medium a tricky prípadoch. Direct preto predstavuje najsilnejší
baseline; naivný RAG v tejto konfigurácii nepriniesol merateľný prínos.

## Najpravdepodobnejšia príčina poklesu

Konfigurácia deklarovala kontext 32 768 tokenov, ale Ollama klient neposielal parameter
`num_ctx`. V 11 RAG behoch bol `prompt_eval_count` presne 4 096, čo silno naznačuje reálny
runtime limit alebo orezanie promptu na 4 096 tokenov. V týchto prípadoch sa prakticky
sústredil celý pokles kvality:

- refaktoring MultiRAG: 7 limitovaných behov, priemer 4,82; ostatných 5 behov priemer 8,71,
- refaktoring Single RAG: 2 limitované behy, priemer 6,69; ostatných 10 behov priemer 8,40,
- testovanie MultiRAG: 2 limitované behy, priemer 4,00; ostatných 10 behov priemer 8,50.

Dlhý a často nesúvisiaci retrieval kontext vytlačil pôvodnú úlohu z efektívneho kontextu.
Model potom riešil alebo kopíroval retrieval príklad namiesto vstupného prípadu. Napríklad
pri `testing_easy_002` MultiRAG vrátil riešenie o inom balíku namiesto testov `NumberParity`;
pri `refactoring_medium_002` skopíroval približne 7 100 znakov nesúvisiaceho
`DeploymentServlet`; pri viacerých refaktoringoch bol výstup prakticky totožný s jedným
retrieved dokumentom.

Retrieval bol navyše málo task-aware. Single RAG používal zmiešanú kolekciu a MultiRAG
rovnako spájal testing a refactoring kolekcie. Pri testovaní bolo v Single RAG 81,7 %
dokumentov z rovnakej úlohy, ale v MultiRAG iba 46,7 %. Pri refaktoringu bolo v Single RAG
iba 10 % dokumentov z rovnakej úlohy. Dlhší retrieval kontext silno koreloval s horším
výsledkom, hoci pri 12 prípadoch na úlohu ide iba o prieskumný signál, nie dôkaz kauzality.

## Obmedzenia vyhodnotenia

Aktuálne smoke skóre je proxy metrika. Testy sa nekompilujú ani nespúšťajú a pravidlá
`validation_rules` zo smoke datasetu sa zatiaľ nevykonávajú. Testovacia metrika kontroluje
najmä prítomnosť `@Test`, assertions a volania cieľovej metódy. Refaktoringová metrika môže
prideliť niekoľko bodov aj nesúvisiacemu, ale syntakticky zdravo vyzerajúcemu kódu. Preto
výsledok nemožno interpretovať ako 72 behaviorálne správnych riešení.

Latencia zároveň vzrástla. Pri refaktoringu bol priemer Direct 7,78 s, Single RAG 12,73 s a
MultiRAG 34,54 s. MultiRAG teda v baseline zhoršil kvalitu aj čas behu.

## Interpretácia do diplomovej práce

Správny záver nie je „RAG nefunguje“. Presnejšia formulácia je:

> Na zmrazenom `baseline_v1` naivný retrieval nezlepšil výsledky. Dlhý, task-agnostic
> kontext v kombinácii s pravdepodobným 4 096-tokenovým runtime limitom spôsobil vytláčanie
> vstupnej úlohy, kopírovanie retrieval príkladov a pokles MultiRAG, najmä pri refaktoringu.

## Canonical `baseline_v2`

Projekt používa iba jeden V2 kontrakt. `baseline_v2` obsahuje:

- explicitné `num_ctx=32768`, rezervu 4 096 výstupných tokenov a reálne vynútenie retrieval
  budgetu,
- metadata filter `task=testing` alebo `task=refactoring` podľa aktuálneho prípadu,
- `top_k=3` aj `per_collection_top_k=3`,
- najviac 768 tokenizer tokenov z jedného retrieved dokumentu,
- záznam odhadovanej aj runtime dĺžky promptu a podozrenia na truncation.

Skrátenie sa vykonáva až pri skladaní promptu, takže existujúca ChromaDB ani jej zmrazené
manifesty sa neprepisujú. Retrieval report zaznamená aplikovaný filter, počet retrieval
tokenov, skrátené dokumenty, finálnu dĺžku promptu a podozrenie na runtime truncation.

Fine-tuning evaluation runner bol nájdený. Používa rovnaké funkcie
`compute_testing_metrics` a `compute_refactoring_metrics` ako smoke experiment. V2 smoke
summary/report preto teraz zobrazuje aj rovnaké agregáty: test quality, coverage proxy,
`code_health_delta_score`, cohesion, coupling, complexity/LOC delta a celkové refactoring
quality. Ide stále o proxy metriky; kompilácia a behaviorálne spustenie ostávajú ďalšou
samostatnou úlohou.

Ďalšími možnými zlepšeniami sú vážený fusion, reranker, identity ochrany, kompilácia a
behaviorálne testovanie. Tieto zmeny sa musia zapísať do nového fingerprintu toho istého
`baseline_v2`, nie vytvárať ďalšie podverzie. `baseline_v1` zostáva nemenný referenčný bod.

## Readiness kontrola V2

Technický dry-run prešiel: fingerprint, fairness, Ollama model digests, tokenizer a všetky
tri Chroma manifesty sú validné. Retrieval probe vrátil tri správne task-filterované
dokumenty pre testing aj refactoring v Single RAG aj MultiRAG.

Audit však odhalil experimentálny problém: index obsahuje iba `mixed`, `testing_db` a
`refactoring_db`. Po aplikovaní canonical-task filtra je opačná tasková kolekcia v MultiRAG
prázdna a `mixed` obsahuje rovnaký taskový korpus ako príslušná špecializovaná kolekcia.
Single RAG a MultiRAG preto vracajú rovnaké evidence dokumenty. V2 je technicky spustiteľný,
ale plný 72-run experiment sa neodporúča, kým MultiRAG nedostane druhý odlišný zdroj, napríklad
`literature_db` alebo `ontology_concepts`, prípadne sa MultiRAG dočasne nevynechá.
