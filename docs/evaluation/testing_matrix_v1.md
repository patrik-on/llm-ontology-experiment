# Testing eval: Methods2Test × baseline / FT / RAG / skills / ontológia

Protokol `methods2test_systems_ontology_v2` (8 ramien; predchádzajúci
`methods2test_systems_skills_v1` sa reprodukuje z jeho pôvodného commitu). Skript pripraví rovnaké
Methods2Test prípady pre všetky systémy, vygeneruje testy, skompiluje ich,
dvakrát spustí cez existujúci Jupiter hodnotiteľ a zmeria JaCoCo coverage.
Nejde iba o textovú podobnosť voči referenčnému testu.

## Spustenie

Z koreňa `llm-ontology-experiment` **vo WSL**:

```bash
# Plán: bez zápisov, bez Ollama API a bez modelových volaní.
.venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py \
  --run-id testing-matrix-20261113 --dry-run

# Predvolený experiment: 100 prípadov × 8 ramien = najviac 800 volaní.
.venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py \
  --run-id testing-matrix-20261113
```

Na minimálny samostatný skúšobný beh použite **nové ID** a `--cases 1` (8 volaní),
menší pilot cez `--cases 5` (40 volaní). Default je 100 prípadov, aby párové
testy (McNemar, Wilcoxon) mali zmysluplnú silu. Počet prípadov
nemožno meniť pri resume; zmenšený default nemení plány už založených behov.
`--prepare-only` pripraví len dáta a vykoná referenčné compile/run/coverage
kontroly, bez generovania. Následne rovnaký príkaz bez tohto prepínača pokračuje.
`--freeze-only` navyše overí model/index identity a uloží všetkých osem skutočných
promptov aj bloky ontológie na prípad; môže volať Ollama metadata a embeddings, nikdy generovanie.
Výber 100 zostaviteľných, neprekrývajúcich sa prípadov môže trvať výrazne dlhšie
než samotné načítanie datasetu; priebežný stav je v `preparation_progress.json`.

Z PowerShellu možno rovnaký vstup spustiť takto (z koreňa projektu):

```powershell
wsl --cd "$PWD" -- .venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py --run-id testing-matrix-20261113 --dry-run
```

### Predpoklady

- Existujúca `.venv_wsl` s projektom a jeho eval/RAG/FT závislosťami.
- WSL Ollama na `http://localhost:11434`, existujúce pinned Qwen a bge-m3 modely.
- Existujúci lokálny HF základ a adaptéry **b2_testing_v3** a **b2_testing_onto**, existujúce Chroma v3
  indexy a ich manifesty podľa projektových konfigurácií.
- Lokálne Methods2Test rich archive a corpus, processed train/val, Java 11,
  Jupiter/AssertJ/Hamcrest a JaCoCo podľa existujúcich pinned eval konfigurácií.
- Vedľajší checkout `../si-context-eval` s `skills/testing/SKILL.md`.
  Pri inom umiestnení použite `--skill-file /cesta/SKILL.md`,
  `--skill-file /cesta/si-context-eval` alebo `SI_CONTEXT_EVAL_REPO`.

Runner nič neinštaluje, nesťahuje, netrénuje a nebuduje indexy. Chýbajúce alebo
zmenené vstupy ohlási ako blokujúci problém, bez náhradného modelu či runtime.
Eval používa Methods2Test harness, nie protokol `si-context-eval`.

## Varianty a férovosť

| Arm | Generovanie | Dodatočný kontext |
|---|---|---|
| `qwen_base` | lokálny Ollama Qwen | žiadny retrieval/skill |
| `onto_project` | ten istý Ollama Qwen | blok projektovej ontológie |
| `skills` | ten istý Ollama Qwen | existujúci testing `SKILL.md` |
| `skills_onto` | ten istý Ollama Qwen | `SKILL.md` + ten istý blok |
| `rag_single` | ten istý Ollama Qwen | existujúca kolekcia `mixed` |
| `ft_testing` | HF Qwen + adaptér `b2_testing_v3` | bez retrievalu/skill |
| `ft_v3_onto` | HF Qwen + adaptér `b2_testing_v3` | ten istý blok |
| `ft_onto` | HF Qwen + adaptér `b2_testing_onto` | ten istý blok |

Blok sa vyrába pri `--freeze-only` iba z dodanej produkčnej triedy
(`ontology.testing_context`, gold test je zakázaný text) a uloží sa do
`cases/<id>/ontology/{block.txt,identity.json}`. Do promptu ho vkladá jediná funkcia
`ontology.with_ontology`, tá istá ako pri tréningových dátach `v3_onto`. Každé FT
rameno má vlastný adaptér z `adapters` v plánovom JSON, jeho identitu v
`hf_identity/<adapter>.json`; pred načítaním sa súbory znova hashujú a ledger
porovná reťazec, ktorý dostal tokenizer, so zmrazeným promptom. `rag_multi` v tomto
protokole nie je.

Hlavné porovnania sú vopred určené páry (`primary_pairs`): `onto_project` vs
`qwen_base`, `ft_v3_onto` vs `ft_testing`, `ft_onto` vs `ft_v3_onto`, `skills_onto`
vs `skills` a `skills_onto` vs `onto_project`. Holm sa robí iba cez tieto páry;
páry naprieč backendmi sú iba opisné.

`skills` je **single-response prompt-context** experiment: rovnaký vstup,
scaffold, solved one-shot príklad, decoding a hodnotiteľ ako baseline, navyše
iba explicitne označený procesný text a pravidlo priority výstupného kontraktu.
Nie je to agent s nástrojmi, `AGENTS.md` ani kombinácia skills+RAG/FT. Skill sa
nevytvára ani neupravuje: jeho pôvodné UTF-8 bytes sa kopírujú do runu a hashujú.
Odporúčania v jeho texte o iteráciách nemenia jednokrokový experimentálny limit.

Všetky varianty používajú `testing-bodies-one-shot-v2`, dva neutrálne body sloty,
4096 output tokenov, context 32768, seed 42 a temperature 0 (FT greedy).
FT používa HF NF4/raw instruction a Ollama Q4_K_M/schema-constrained decoding:
ide o **porovnanie systémov**, nie izolovaný kauzálny efekt LoRA. Dlhší skills
prompt nie je tokenovo párovaná placebo kontrola. Existujúce retrieval obmedzenia
sa nemenia; pri prekročení budgetu sa prompt potichu netruncuje.

## Dáta

Používa sa oficiálny Methods2Test **EVAL**, nie vyhradený TEST. Výber v poradí
archívu a s capom desať na projekt opätovne používa existujúci model-free
selector: odmieta historicky vybrané/explorované ID, train/val projekty a
normalizované focal/reference zhody/containment v aktuálnom train/val a skutočných
RAG dokumentoch. Rich a corpus kód musia súhlasiť. Missing lineage zostáva unknown.

Prijíma len podporované verejné statické JDK-compatible metódy, ich nezmenené
referencie a podporovaný potrebný kontext. Referencia musí skompilovať, pozitívne
prejsť a preukázateľne zavolať správny focal JVM overload cez JaCoCo **pred**
volaním modelu. Gold ostáva evaluator-only, nikdy nevstupuje do promptu/indexu.
Ak nemožno pripraviť požadované N, generovanie sa nespustí s menšou vzorkou.

Je to convenience/dependency-filtered **extracted-method validation**, nie build
pôvodných projektov ani náhodná reprezentatívna vzorka. Snapshot audit nedokazuje
neprítomnosť v historickom pretrainingu modelu.

### Hranice datasetu

Do testing skóre patria iba prípady aktuálnej Methods2Test matice. Predtým
explorované ID sú uložené ako vylúčenia v konfigurácii, nie ako zachované staré
výsledky. Oficiálny TEST reserve ostáva nedotknutý.

## Výstupy, metriky a resume

Všetko nové je pod `artifacts/evaluation/runs/<run-id>/`:

- `matrix_plan.json`, `selection.json`, `leakage_audit.json`, príprava a odmietnutia;
- `context/SKILL.md` a `context/identity.json` s cestou, bytes a SHA-256;
- `freeze.json`, model/adapter/index identity, source snapshot a všetky skutočné
  `cases/<id>/frozen_prompts/<arm>/prompt.txt` ešte pred generovaním;
- `predictions/<arm>/dispatch.json`, raw server/model výstupy, prípadné chyby,
  zložený Java zdroj a `completion.json`;
- dvojnásobná kompilácia/spustenie, XML, method/class line/branch coverage;
- `progress.json`, `reports/aggregate.json` a čitateľný `reports/summary.md`.

Report uvádza schema/assembly/truncation, kompiláciu, skutočne spustené testy,
class pass, instrumented focal invocation, repeat stability, coverage a párové
rozdiely všetkých desiatich dvojíc systémov. Coverage failing tried je iba
diagnostická; chýbajúce meranie je null s dôvodom, branchless metódy sú N/A.
Nezavolané bunky nie sú failures ani passing. Neexistuje buggy revision ani
mutation kampaň, preto sa netvrdí fault detection.

Rovnaký príkaz s rovnakým ID pokračuje len nedispatchovanými bunkami a overí
zmrazené vstupy. Každá bunka má najviac jeden pokus; chyby ostávajú v menovateli.
Prerušená charged bunka sa **nikdy** automaticky neopakuje; jej systém sa pozastaví
ako unresolved. Prázdna/transport/API anomália zastaví dotknutý systém, bežné
neplatné JSON/Java/compile/assertion výstupy nie. GPU kroky sa vykonávajú sériovo;
nové matrix runy zdieľajú flock. Obe matice musia rešpektovať spoločný GPU zámok.
Pri neúplnom matrixe je exit code 2. Nové ID zakladá nový experiment, nie opravu
zlyhaní predchádzajúceho.

Report bez generovania/spúšťania:

```bash
.venv_wsl/bin/python scripts/benchmarks/run_testing_matrix.py \
  --run-id testing-matrix-20261113 --report-only
```

V projekte sú podporované iba aktuálne dve matice. Source freeze musí zodpovedať
aktuálnemu kódu; po zmene infraštruktúry sa pri prípravách s nulovým dispatchom
vytvorí nový zdrojový snapshot. Dokončené modelové výsledky sa nikdy spätne
nepodpisujú novými hashmi.

## Aktuálny stav

Zostávajúci pripravený testing beh je
`testing-matrix-preparation-check-20261113`: jeden EVAL prípad `5973732_198`,
päť skutočných promptov a **0 generovaní**. Patrí k protokolu
`methods2test_systems_skills_v1`; nový protokol potrebuje nové run ID.
Referenčné a evaluator QA dôkazy sú súčasťou tohto run rootu; ručne napísané
kontroly nepredstavujú modelové skóre. Model-free QA súhrn je v
`readiness/evaluator-qa.json`. Staršie piloty, eval skripty a výsledky boli odstránené.

Po konsolidácii celá zostávajúca testovacia sada prešla: **288 passed, 2 skipped**.
Skips sú voliteľné integračné kontroly. Ruff a whitespace kontroly tiež prešli.
