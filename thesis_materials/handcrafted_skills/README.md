# Historický handcrafted experiment: SKILL.md a AGENTS.md

Archivované 13. 11. 2026 z vedľajšieho repozitára `si-context-eval`.
Ide o experiment na ručne vytvorených Java projektoch, **nie** o starší
`data/smoke/` dataset v tomto repozitári a nie o dnešný Methods2Test/SWE protokol.

## Čo je uložené

- [Posledný reportovací audit, pôvodné znenie](grader-v6-reporting-original.md)
  z 21. 10. 2026; jeho [kópia s pôvodným relatívnym rozložením](evidence/si-context-eval/docs/audits/grader-v6-reporting.md)
  má funkčné odkazy na priložené metodické a výsledkové dôkazy.
- [Metodika](evidence/si-context-eval/docs/methodology.md),
  [agent-v2 protokol](evidence/si-context-eval/docs/agent-v2.md) a
  [kritický audit pilotu](evidence/si-context-eval/docs/audits/pilot-v5-audit.md).
- [Najnovší historický report JSON](evidence/si-context-eval/runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/historical-report.json)
  a [jeho overenie](evidence/si-context-eval/runs/reports/grader-v6-reporting/20261021T143538Z-62c6c9cc/verification-summary.json).
- [Pôvodné experimenty](evidence/si-context-eval/runs/experiments/),
  [reporty](evidence/si-context-eval/runs/reports/) a
  [kalibračné dôkazy](evidence/si-context-eval/runs/calibration/).
- Zdrojová snímka metodiky, graderov, zadaní, projektov a oboch skillov
  v `evidence/si-context-eval/`; je to kontext na čítanie archívu, nie tretí
  podporovaný runner. Aktívne skilly ostali nezmenené v `../si-context-eval/skills/`.
- [Inventár presunu a SHA-256](archive_manifest.json). Výsledkové stromy boli
  presunuté, kontextové zdroje skopírované; pri overení sa kontroloval každý súbor.

## Čo experiment skúmal

Ručne pripravené úlohy porovnávali štyri podmienky: bez kontextu, procesný
`SKILL.md`, modulové `AGENTS.md` a ich kombináciu. Dve vetvy obsahujú po
12 úloh: testing nad zámerne chybnou implementáciou a refactoring nad Java
projektom s code smells. Zadania, správne referencie a skryté oracles sú
oddelené od modelového vstupu. Protokoly `agent` a `agent-v2` sa nesmú zmiešať;
agent-v2 umožňoval ohraničenú nástrojovú interakciu a validačnú opravu.

Posledné modelové kohorty z 6. 10. 2026 sú štyri testing podmienky pre
`gpt-oss:20b`, `agent-v2`, po 12 pokusov. Archív obsahuje aj predchádzajúce
Qwen kohorty, pretože posledný report inventarizuje všetkých **240 pokusov**,
nie len túto poslednú štvoricu. Októbrové kalibračné overenia nie sú nové
modelové experimenty.

## Čísla a správna interpretácia

Posledná modelová štvorica (GPT-OSS 20B, testing, agent-v2, 6. 10. 2026),
podľa opraveného historického reportu z 21. 10. 2026:

| Kontext | Úspechy / všetky začaté pokusy | Modelové neúspechy | Z toho bez kandidáta |
|---|---:|---:|---:|
| Bez kontextu | 4/12 | 8 | 2 |
| SKILL.md | 3/12 | 9 | 4 |
| AGENTS.md | 4/12 | 8 | 4 |
| Kombinácia | 7/12 | 5 | 3 |

Sú to jednopokusové výsledky na rovnakých 12 ručne navrhnutých úlohách,
nie štatistický dôkaz všeobecnej prevahy kombinácie. Počty bez kandidáta sú
už zahrnuté medzi neúspechmi, nepripočítavajú sa druhýkrát.

Posledný read-only report eviduje **94 úspechov a 146 modelových neúspechov**
z 240 historických pokusov; 13 neúspechov je bez kandidáta. Je to inventár
rôznych kohort, nie jedna porovnateľná úspešnosť ani dôkaz účinku skillov.
Pri GPT-OSS combined/testing treba uvádzať **7/12**, nie starý podmienený
výsledok 7/9, ktorý nezahŕňal tri generácie bez kandidáta.

Historické automatické refactoring úspechy sú podľa **legacy** kontraktu.
Novší objective profil bol overený iba pre `r-api-quantity`; historické
modelové výstupy neboli spätne prehodnotené. Testing overuje aj určenú chybu,
ale z toho nevyplýva všeobecná schopnosť odhaľovania ľubovoľných chýb.
Reportovacie/kalibračné kontroly oddeliť od úspechov modelov.

**Dnešné `skills` rameno je iný experiment:** pridá existujúci skill do jednej
odpovede bez nástrojov, AGENTS a opráv. Historické skóre nemožno preniesť
na súčasné matice ani s nimi zlúčiť do jednej tabuľky úspešnosti.

## Presun a reprodukovateľnosť

`runs/experiments`, `runs/reports` a `runs/calibration` boli presunuté z
`si-context-eval` do zodpovedajúcich ciest v tomto archíve. Cache a unit logy
neboli presunuté. V pôvodnom repozitári sú navigačné upozornenia.
Absolútne Windows/WSL cesty v pôvodných JSON/logoch sú **historické**:
prefix `.../si-context-eval/runs/` sa pri čítaní mapuje na
`thesis_materials/handcrafted_skills/evidence/si-context-eval/runs/`.
Obsah výsledkov, grade, modelové odpovede a ich hashe sa neprepisovali.

Archív je dôkazový balík, nie prenositeľné runtime prostredie. Neobsahuje
modely, Maven cache ani Git históriu. Nespúšťať v ňom nové experimenty.
Odkazy v pôvodnom samostatnom znení auditu sú historické; na navigáciu
použiť vyššie uvedenú kópiu so zachovaným rozložením.
