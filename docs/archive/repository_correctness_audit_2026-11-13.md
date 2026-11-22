# Audit správnosti repozitára — 2026-11-13

## Záver

**Nenašiel som potvrdenú P0 chybu, ktorá by automaticky zneplatňovala všetky výsledky. Našiel som jednu vysoko prioritnú chybu prípravy tréningových sekvencií a tri relevantné problémy evaluácie/reportovania.** Pred väčším porovnávaním systémov odporúčam vyriešiť tieto body. Zelená regresná sada ich dnes nepokrýva.

Ide o audit aktuálneho pracovného stromu nad HEAD `9c380e2f64900e3d12dc06aacdd693accc1c4f23`, vrátane necommitnutých nových modulov a odstránení. Nie o audit samotného commitu. Existujúce používateľské zmeny zostali nedotknuté; tento report je jediný pridaný súbor v repozitári.

### Rozsah a overenie

- Hlavný tok oboch aktuálnych matíc: výber dát, prompty, dispatch/budget/resume, extrakcia odpovedí, kompilácia a JUnit, JaCoCo, detekcia refactoringu, agregácie a reporty.
- Doplnkovo tréningové tokenizovanie/maskovanie, datasetové splity, retrieval/fúzia/token budget a väzby konfigurácií. UI a ingestion boli kontrolované orientačne, nie vyčerpávajúcim integračným auditom.
- WSL: `.venv_wsl/bin/python -m pytest -q` → **288 passed, 2 skipped in 32.08s**.
- WSL: `.venv_wsl/bin/ruff check src scripts tests` → **All checks passed**.
- Dodatočné izolované reprodukcie v dočasných adresároch; bez generovania odpovedí, tréningu, sťahovania či prebudovania indexu. Reprodukcie evaluátora používajú mockované merania; nejde o nové výsledky modelov ani nové Java integračné behy.
- Počty tréningových tokenov merané skutočným lokálnym Qwen tokenizerom, bez načítania váh modelu.
- Oba aktuálne run adresáre obsahujú **0 dispatchov**. Sú to prípravy, nie experimentálne skóre; audit nepreukázal poškodenie už existujúcich aktuálnych modelových skóre.

## Nálezy podľa priority

### 1. P1 — Dlhé tréningové odpovede vytlačia takmer celý vstup

**Miesto:** `src/llm_ontology/finetuning/training/finetuning.py:258–270`, `configs/shared/models/qwen25_coder_7b_hf_wsl.yaml:12`.

Pri prekročení limitu sa odpovedi pridelí až `max_seq_length - 1` tokenov. Zvyšný prompt sa ponechá iba od konca. Ak má odpoveď aspoň 2047 tokenov, pri limite 2048 zostane **jeden token promptu**: model už nevidí Java vstup ani zadanie, ale stále sa učí odpoveď. Ešte dlhšia odpoveď sa navyše odreže bez ukončenia. Rovnaká transformácia sa používa na validačné príklady.

Prepočet aktuálnych `train.jsonl` + `val.jsonl`, limit 2048, tokenizer z konfigurovaného lokálneho Qwen modelu:

| Dataset | Príklady | Skrátený prompt a/alebo odpoveď | Len 1 token promptu a skrátená odpoveď |
|---|---:|---:|---:|
| testing | 4500 | 1 | 1 |
| refactoring | 5078 | 1518 | 184 |

**Dopad:** významný problém najmä pre refactoring FT. Časť učenia prestáva byť podmienená riešeným kódom; validačný loss potom nehodnotí presne požadovanú schopnosť. Nie každý skrátený príklad je nevyhnutne nepoužiteľný, ale 184 príkladov s jediným tokenom zadania jednoznačne nie je plnohodnotná instruction tuning dvojica.

**Odporúčanie:** nepripustiť zničenie celého zadania. Pre príliš dlhé dvojice zvoliť explicitnú politiku: vyradiť ich alebo použiť väčší limit podľa tokenovej distribúcie a VRAM. Uchovať kompletný nevyhnutný vstup a dokončenú odpoveď; zapisovať počty vyradených/skrátených príkladov a efektívne tokenové dĺžky po splitoch. Regresia má kontrolovať zachovanie zadania, nielen existenciu nemaskovaných labelov.

**Hranica dôkazu:** počty sa týkajú dnešných súborov. Nedokazujú, že historický adaptér videl presne tie isté bajty a verziu tokenizovania. Pred rozhodnutím o pretrénovaní treba overiť jeho uloženú konfiguráciu/provenienciu; automatické pretrénovanie nie je súčasť auditu.

### 2. P2 — Nevyhodnotený dispatch sa vykazuje ako zlyhanie modelu

**Miesto:** `src/llm_ontology/benchmarks/methods2test_statistics.py:342–354`.

`_row()` odvodzuje neznámy výsledok z `not attempted or assembled`. Ak existuje `dispatch.json`, ale po páde procesu ešte neexistuje dokončenie ani `generated.java`, nastaví `class_pass=False`, `compiled=False` a ďalšie záporné metriky. Nečíta pritom `completion.json` na rozlíšenie skutočne ukončeného zlého výstupu od rozpracovaného transportu.

**Reprodukcia:** výber s jedným ID a jediný prázdny `dispatch.json`, bez odpovede, completion a metrics → agregácia vrátila `actual_calls=1`, `class_pass=false`, `compiled=false`.

**Dopad:** aj bežný priebežný report počas generovania alebo report po prerušení znižuje úspešnosť a párové porovnania, hoci výsledok ešte nie je známy. Finálny príznak úplnosti ostáva pri chýbajúcom completion správne false, ale čiastkové sadzby a success credit už obsahujú neodôvodnený neúspech.

**Odporúčanie:** ponechať dispatch v nákladovom rozpočte, ale výsledok označiť `pending/interrupted_unresolved` a metriky `null`, kým neexistuje terminálny dôkaz. Ukončený nevalidný modelový výstup naďalej počítať ako neúspech. Oddeliť infra chyby od kvality modelovej odpovede.

### 3. P2 — Nereprodukovateľné coverage dostáva kredit podľa prvého opakovania

**Miesto:** `src/llm_ontology/benchmarks/methods2test_metrics.py:59–65`; doplnková kontrola podpisov v `methods2test_execution.py:132–139`.

Metriky vypočítajú `repeat_coverage_equal`, ale tento výsledok nepoužijú pri výbere primárneho coverage. Ak obe testovacie triedy prejdú, prevezmú coverage prvého behu. `repeat_stable` pôvodne porovnáva iba statusy a súhrnné počty, nie samotné coverage.

**Reprodukcia:** dve mockované úspešné merania so zhodnými počtami testov a rozdielnym coverage → `class_pass=true`, `repeat_stable=true`, `repeat_coverage_equal=false`, primárne coverage z prvého merania. Samostatná reprodukcia rozdielnych XML podpisov ukázala `repeat_stable=false`, ale `class_pass=true` a primárne coverage zostali zachované. Druhá reprodukcia overuje obrannú logiku, nie tvrdenie, že pevný dvojmetódový scaffold bežne mení mená testov.

**Dopad:** napríklad náhodné vstupy môžu v dvoch úspešných behoch zasiahnuť rozdielne vetvy. Report potom prezentuje závislé od poradia zvolené coverage ako štandardnú porovnateľnú hodnotu.

**Odporúčanie:** raw class pass môže zostať samostatnou metrikou „oba behy prešli“, ale stabilitu výsledku a coverage treba hodnotiť oddelene. Pri rozdielnych meraniach uviesť nestabilitu a zvoliť vopred deklarovanú politiku: primárne coverage neznáme, alebo explicitný konzervatívny/agregovaný výsledok. Nevyberať potichu prvý beh. Pri rozdielnych testových podpisoch nepriznávať verified/stable success.

### 4. P2 — Testing RAG má 15× kratší transportný limit než baseline/skills

**Miesto:** `configs/retrieval/ollama_bge_m3_v3.yaml` (`llm.timeout_seconds: 120`), `benchmarks/evaluation_generation.py` (`generate_rag`), `benchmarks/matrix_support.py:274` (`timeout_seconds=1800`).

Testing RAG provider preberá limit 120 sekúnd, direct a skills majú 1800 sekúnd. Všetky používajú ten istý Qwen a výstupný limit 4096 tokenov; RAG má typicky dlhší vstup. Refactoring matica má pre svoje Ollama ramená jednotných 1800 sekúnd.

**Dopad:** ak sa RAG odpoveď nevráti počas 120-sekundového socketového timeoutu, klient odíde a dané rameno sa fail-stopne; direct môže pokračovať oveľa dlhšie. To môže vytvoriť neúplnú maticu kvôli rozdielu infra limitu, nie schopnostiam systémov. Či sa to stane na konkrétnej GPU, audit bez generovania nemeral. Socket timeout nie je presný univerzálny wall-clock deadline, ale pri ne-streamovanej odpovedi je rozdiel prakticky relevantný.

**Odporúčanie:** jeden explicitný transportný/generačný limit v pláne matice pre porovnávané Ollama varianty. Zapisovať timeout ako infra udalosť, nie dôkaz nekvalitného kódu. Nezvyšovať kvôli tomu limit embeddingov bez dôvodu.

## Menší, ale konkrétny retrieval problém

`retrieval/pipeline.py:114,197,398` najskôr aplikuje odhad `ceil(chars/4)` a zahodí celé dokumenty. `inference/experiment_runner.py:244` až potom použije presný tokenizer a pair-aware truncation, ale už len nad preživšími dokumentmi. Dokument odstránený hrubým filtrom sa tak nikdy nedostane k presnému budgeteru.

Izolovaný 52000-znakový dokument pri budgete 12000: starý filter ponechal 0 dokumentov; existujúci budgeter nad pôvodným ranked zoznamom dokázal ponechať 1 skrátený dokument. SWE matica už obsahuje lokálny workaround cez `found.trace.retrieved_documents`; spoločný testing runner nie.

**Aktuálny dopad nepreukázaný:** v dnešnom indexe je maximum 24083 znakov pre mixed/refactoring a 7298 pre testing, teda uvedený individuálny 52000-znakový príklad sa v ňom nenachádza. Filter však môže zahadzovať aj dokumenty pri naplnení súhrnného budgetu. Aktuálny pripravený testing prípad má tri krátke dokumenty a tento problém pri ňom nenastal. Nie je to dôvod označiť jeho prípravu za neplatnú.

Odporúčanie: zjednotiť existujúcu logiku a presný výber robiť raz nad ranked top-k. Nemení sa tým automaticky požadované top-k ani retrieval stratégia; zmena protokolu sa musí verziovať.

## Výkon a údržba — bez nového frameworku

1. **Nevyhadzovať Ollama model po každom prípade.** Oba ledgery nastavujú `keep_alive=0` pri každom dispatchi. Pri viacerých prípadoch to opakuje načítanie váh. Držať model počas jedného Ollama ramena a explicitne ho uvoľniť pred HF ramenom zachová správu VRAM a zníži opakované load overhead. Najprv oddeliť a zmerať load/prefill/decode čas; netvrdiť univerzálne percento zrýchlenia.
2. **Nečítavať zbytočne celé váhy a cache pri každom kroku.** SWE `verify()` opakovane hashuje modelové váhy a celý zmrazený balík vrátane Maven cache. Overovanie zachovať pri začatí/resume/report-only, počas jedného exkluzívneho procesu overovať zmenené vstupy alebo používať premyslenú cache hashov. Neodstrániť pinning len kvôli rýchlosti.
3. **Zdieľať tokenizer/klientov v jednom ramene.** Direct helper vytvára token counter nanovo na každý prípad; RAG znovu zostavuje runtime objekty. Cache tokenizera podľa skutočnej identity a opätovné použitie klientov nevyžaduje zmenu promptov.
4. **Aktívne pracovné/build adresáre držať na Linux FS.** SWE už checkouty správne umiestňuje pod `/home/patrik/...`; rovnaký princíp možno využiť pri budúcich veľkých prípravách/indexoch. Výsledné dôkazy kopírovať/exportovať do repozitára. Pred presunom zohľadniť uložené absolútne cesty a existujúce freeze súbory, nič automaticky nepresúvať.
5. **Spoločný typed stav bunky a jedna budget logika.** Zdieľať mechaniku pending/dispatched/completed/evaluated a pravidlá unknown/infra/model failure medzi dvoma maticami. Nezlučovať task-specific vedecké protokoly do ďalšieho veľkého frameworku. Najvyššiu návratnosť majú regresie vyššie uvedených prechodov.
6. **Zjednotiť význam časových metrík.** Testing agregácia pri Ollama používa server `eval_duration`, pri HF hľadá iné polia; nejde automaticky o porovnateľnú end-to-end latenciu. Oddeliť načítanie, retrieval, prefill, decode a celý wall time. Pri `keep_alive=0` reportovať aj cold-start režim.

Tieto návrhy využívajú už prítomné knižnice a helpery; audit nenavrhuje platenú službu ani nový vlastný eval framework.

## Čo je spravené dobre / čo nepovažujem za bug

- Java vykonanie odlišuje kompiláciu, no-tests, aborted/container failures, nenulový exit a normálny pass. Chýbajúca coverage nie je automaticky vymyslená nula.
- Coverage meria pinovaný JaCoCo nad produkčnou triedou; testy nie sú započítané do coverage produkcie. Vybraná metóda má uložený JVM descriptor.
- SWE úspech vyžaduje viac než obyčajné zelené testy: detegovanú operáciu na správnom mieste, build a opakované testy so zachovaným podpisom. No-op je odmietnutý. QA obsahuje referenciu a negatívne kontroly.
- Jednorazové dispatchy, žiadne opravy/retry a porovnanie zmrazených promptov pomáhajú reprodukovateľnosti. Staré odstránené protokoly som neobnovoval.
- Datasetové splittery majú explicitné group pravidlá. Samotné konštatovanie „žiadny leakage“ by napriek tomu bolo príliš silné: SWE sám správne deklaruje iba basic overlap screen a nevie garantovať nevidenosť repozitárov ani historický pretraining.
- Päť convenience prípadov, viac prípadov z rovnakého projektu, extrahované Methods2Test metódy a odlišné HF/Ollama backendy sú **deklarované metodické obmedzenia**, nie tajné implementačné bugy. Výsledky nemajú byť interpretované ako univerzálny rebríček, dôkaz fault detection alebo izolovaný účinok FT adaptéra.
- V aktuálnom jedinom pripravenom testing prípade Single-RAG a MultiRAG vybrali rovnaké tri document IDs. To môže byť legitímne; samotný rozdiel architektúr nezaručuje rozdielny kontext ani lepšie skóre.

## Odporúčané poradie

1. Opraviť politiku dlhých tréningových dvojíc a uložiť tokenové štatistiky/provenienciu.
2. Opraviť unknown stavy a pravidlá stability/primárneho coverage; doplniť cielené regresie.
3. Zjednotiť timeouty testing variantov a explicitne zaznamenať backend/runtime limity.
4. Až potom zmerať výkon a odstrániť opakované načítavanie modelu/tokenizera; pri zmenách generovania alebo výberu kontextu vytvoriť novú verziu protokolu a nový run ID.

**Audit nemenil implementáciu, datasety, konfigurácie, indexy ani modely.** Nové úplné experimenty a história tréningu neboli znovu vykonané; úplnú absenciu ďalších chýb nemožno z tejto kontroly garantovať.
