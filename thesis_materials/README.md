# Podklady na písanie diplomovej práce

Tento priečinok zhromažďuje **metodické vysvetlenia, historické výsledky,
reporty a dôkazy**, z ktorých možno čerpať pri písaní práce. Nie je to ďalší
eval framework, pracovný adresár runnerov ani tréningový/RAG dataset.

## Rozcestník

- [Návrh aktuálnych evaluácií a runnerov](reports/evaluation_design_2026-11-13.md)
  — výskumné otázky, porovnávané systémy, dáta, hodnotenie, férovosť a limity.
- [Handcrafted experiment so SKILL.md a AGENTS.md](handcrafted_skills/README.md)
  — historické výsledky, posledný opravený report a metodický kontext.
- [Smoke baseline v1](reports/smoke_baseline_v1_2026-08.md) a
  [smoke baseline v2](reports/smoke_baseline_v2_2026-08-21.md) — historické
  reporty Direct/RAG/MultiRAG na proxy metrikách; motivácia súčasných matíc.
- [Aktuálne prevádzkové runbooky](../docs/evaluation/README.md)
  — autoritatívne príkazy pre dnešné dve matice.

## Ako sem ukladať ďalšie materiály

Pri reporte uviesť dátum, zdrojový experiment/run ID, protokol, model,
menovateľ a obmedzenia interpretácie. Oddeliť merania modelov od kontroly
infraštruktúry a vysvetľujúceho textu. Historické merania nemeníme ani spätne
neprepočítavame bez samostatne označeného nového reportu.

Aktívne výsledky oboch matíc naďalej patria iba do
`artifacts/evaluation/runs/<run-id>/`. Sem môžu ísť ich **označené finálne
exporty a interpretácie**, nie druhá živá kópia runu. Starý handcrafted
experiment je archívny podklad; jeho výsledky sa nepripočítavajú k novým maticiam.

Surové historické dôkazy pod `handcrafted_skills/evidence/` sú lokálne a
ignorované Gitom (rovnako ako pôvodné `si-context-eval/runs/`). Čitateľné reporty,
inventár hashov a tento rozcestník nie sú ignorované. Pri prenose projektu je
potrebné preniesť dôkazy osobitne; samotný Git checkout ich neobsahuje.
