# Súlad tréningu a evaluácie FT adaptérov

Nov 18, 2026 · @Patrik

Potvrdzujem: ramená `ft_testing` a `ft_refactoring` sa hodnotia na úlohe, ktorú adaptéry pri tréningu nikdy nevideli. Tréning učil vrátiť holý Java kód na krátky slovenský pokyn, evaluácia chce striktný JSON s inou štruktúrou, dostáva dlhý anglický kontrakt a parsuje výstup cez `json.loads` bez tolerancie. FT ramená preto takmer isto skončia ako `model_output_failure` ešte pred kompiláciou, a výsledok by meral formát, nie efekt dotrénovania. Analýza je z kódu na commite `0f6adc6`; nič sa nemenilo.

## Testing: b2\_testing\_v2 vs. testing matica

Adaptér sa učil „focal metóda → celá JUnit testovacia metóda ako text“. Matica od neho chce „celá trieda + scaffold → JSON s dvoma telami Jupiter testov“. Zhoduje sa iba obal `### Instruction / ### Input / ### Response`.

| Aspekt | Tréning (`data/processed/testing/train.jsonl`) | Evaluácia (`testing_matrix.py`, rameno `ft_testing`) |
| --- | --- | --- |
| Inštrukcia | „Vygeneruj JUnit test pre nasledujúcu Java metódu.“ (SK, 1 veta) | Anglický `CONTRACT` z `testing_bodies_v1.py` + prázdny scaffold + project context + JSON schéma + one-shot demo blok |
| Vstup | `src_fm`: iba focal metóda v jednom riadku | Celá obalená produkčná trieda (package, importy, trieda) |
| Dĺžka promptu | priemer cca 160 tokenov | rádovo 1,5–3 tisíc tokenov (kontrakt + demo + trieda), odhad z kódu |
| Požadovaný výstup | Holý Java kód: `@Test public void ...() { ... }` | Striktný JSON `{"testCase1": "...", "testCase2": "..."}` |
| Obsah výstupu | Celá metóda s anotáciou a signatúrou | Iba vnútro tela; anotácie a deklarácie metód `validate_body` zakazuje |
| Počet testov | 1 | presne 2 |
| Framework | Methods2Test gold je prevážne JUnit 4, často AssertJ/Hamcrest `assertThat` | JUnit 5 Jupiter, staticky importované iba `Assertions.*` |
| Parsovanie | — | `parse_testing_bodies` = `json.loads` bez odstránenia textu či fence |
| Dekódovanie | — | HF NF4, bez obmedzenia na schému; base/RAG/skills idú cez Ollamu so schema-constrained JSON |

Dôsledok: model vráti `@Test public void ...` (to sa naučil), `json.loads` zlyhá a bunka je `model_output_failure`. Aj keby JSON trafil, `assertThat` a anotácie by neprešli validáciou tela alebo kompiláciou.

Poznámka k dátam: `val.jsonl` (checkpoint selection) pochádza z oficiálneho Methods2Test EVAL splitu, z ktorého sa vyberajú aj evaluačné prípady. Záznamy sú vylúčené auditom, ale projektový prekryv val vs. eval treba ešte overiť v `leakage_audit.json`.

## Refactoring: b2\_refactoring\_v2 vs. refactoring matica

Aj tu adaptér vie iba „kód pred → kód po“ ako holý text, kým matica chce JSON s celým súborom a presne zadaným cieľom. K tomu 50 zo 60 ML4Ref prípadov má typ, ktorý bol v tréningových dátach označený ako `unknown`.

| Aspekt | Tréning (`data/processed/refactoring/train.jsonl`, 4 478 záznamov) | Evaluácia (`refactoring_matrix.py`, rameno `ft_refactoring`) |
| --- | --- | --- |
| Inštrukcia | „Vygeneruj refaktorovanú verziu ... podľa typu refaktoringu: X.“ (SK) | Anglický `CONTRACT` + operácia + presná požadovaná zmena (napr. nové meno) + cieľové riadky + povolený `file_path` + JSON schéma |
| Čo má model urobiť | Uhádnuť, čo v commite vzniklo (nové meno, hranice extrakcie) | Vykonať jednu konkrétne zadanú operáciu na konkrétnom cieli |
| Vstup | ML4Ref: celý súbor do 12 000 zn.; MaRV: úryvok | MaRV/ML4Ref: kontextový úryvok („supplied context unit“); SWE: celý súbor; medián 3,1 tis. zn., max 17,7 tis. |
| Požadovaný výstup | Holý Java kód | Striktný JSON `{"file_path", "refactored_code"}`, parsovaný `json.loads` v `parse_answer` |
| Dĺžka sekvencie | `max_seq_length` 2 048; 30 % príkladov skrátených, pri 488 ostane z promptu max. 128 tokenov | kontext 32 768, `max_new_tokens` 8 192 |
| Typy operácií | ML4Ref: 35 % Move Class, 16 % `unknown`; MaRV: Extract Method, Rename Method, Rename Variable, Remove Parameter | 11 typov, viď tabuľku nižšie |

**Typy operácií v evaluácii a ich pokrytie v tréningu** (stav podľa `docs/datasets/data_audit_report.md`, dáta z pred v2 tréningu):

| Zdroj | Operácia | Prípadov | V tréningu |
| --- | --- | --- | --- |
| ML4Ref | Extract Variable | 10 | iba ako `unknown` |
| ML4Ref | Inline Variable | 10 | iba ako `unknown` |
| ML4Ref | Rename Parameter | 10 | iba ako `unknown` |
| ML4Ref | Parameterize Variable | 10 | iba ako `unknown` |
| ML4Ref | Replace Variable With Attribute | 10 | iba ako `unknown` |
| ML4Ref | Rename Class | 10 | áno, 3 % |
| MaRV | Rename Variable / Rename Method / Extract Method / Remove Parameter | 35 | áno |
| SWE | Extract Method / Inline Method | 5 | áno (Inline Method 1,3 %) |

Parsér v `ml4refactoring.py` dostal týchto päť typov až v commite `d274973` (18. 11. 2026). Adaptéry v2 sa trénovali na starších JSONL, takže pre ne bola inštrukcia „typ refaktoringu: unknown“. Lokálne JSONL v Windows klone repa nie sú (sú iba vo WSL), preto som počty neoveril priamo na dátach.

Dôsledok: rovnako ako pri testingu skončí FT väčšina buniek na parsovaní JSON. Aj s opraveným formátom je 50 z 95 štruktúrnych prípadov pre adaptér neznámy typ úlohy.

## b1\_shared\_v2

Spoločný adaptér má rovnaký formát ako `b2_*` (holý kód, SK inštrukcie, 2 048 tokenov), takže má všetky nesúlady z oboch tabuliek vyššie. Navyše:

- `combined` = 4 000 Methods2Test + 4 000 ML4Ref, **bez MaRV**. Na 35 MaRV prípadoch má teda menšie pokrytie než `b2_refactoring_v2`.
- Vyváženie je podľa riadkov, nie tokenov: ML4Ref tvorí cca 85 % tokenov, takže testing časť je v tréningu slabá.
- V aktuálnych maticiach sa nepoužíva vôbec (ramená sú iba `ft_testing` a `ft_refactoring`). Porovnanie shared vs. špecializovaný zo zadania zatiaľ nemá meranie.

## Čo s tým

Odporúčam možnosť B: pretrénovať adaptéry na dátach v presne tom formáte, ktorý matica používa. Len tak meria rameno FT efekt dotrénovania.

| Možnosť | Čo sa zmení | Cena | Čo potom FT rameno meria |
| --- | --- | --- | --- |
| A. Prispôsobiť evaluáciu adaptérom | FT prompt = tréningový formát, výstup holý kód, obal do scaffoldu/JSON urobí kód | malá, bez tréningu | FT dostane iný prompt než ostatné ramená; testing aj tak nesedí (1 celá metóda JUnit 4 vs. 2 Jupiter telá) |
| B. Pretrénovať v2 → v3 v eval formáte (odporúčané) | Tréningové záznamy sa vyrenderujú tou istou funkciou ako eval prompt (`ft_case` / `instruction(case)`), gold sa zabalí do JSON, Jupiter scaffold, opravený parsér typov, `max_seq_length` aspoň 8 192 | 3 tréningy na GPU + úprava builderov datasetu | čistý efekt FT pri rovnakom kontrakte |
| C. Nechať tak a popísať | nič | žiadna | iba „adaptér nedodrží nový kontrakt“; pre diplomovku slabé |

Pri B sa oplatí zároveň doplniť kontrolné rameno `qwen_base_hf` (rovnaký HF NF4 backend bez adaptéra, bod D18 auditu) a rameno `ft_shared`. Potom je rozdiel FT vs. base čistý aj voči backendu.

Otvorené otázky na overenie vo WSL:

- [ ] Počet záznamov s `refactoring_type: unknown` v `data/processed/refactoring/train.jsonl` a `combined/train.jsonl`
- [ ] Projektový prekryv `testing/val.jsonl` s vybranými eval prípadmi v `leakage_audit.json`
- [ ] `training_summary.json` adaptérov: dátum tréningu a použitý `max_seq_length`
