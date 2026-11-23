# Podklady na písanie diplomovej práce

Tento priečinok zhromažďuje **metodické vysvetlenia, historické výsledky,
reporty a dôkazy**, z ktorých možno čerpať pri písaní práce. Nie je to ďalší
eval framework, pracovný adresár runnerov ani tréningový/RAG dataset.

## Rozcestník

### Analýzy a porovnania finálnych behov

Každá analýza má vlastný priečinok `<dátum>_<téma>/` s krátkym popisom v `README.md`.

| Dátum | Priečinok | Čo obsahuje |
|---|---|---|
| 2026-11-21 | [preco_ontologia_nepomohla](2026-11-21_preco_ontologia_nepomohla/README.md) | predbežné hypotézy, prečo ontológia ani skill nepriniesli zlepšenie |
| 2026-11-22 | [vysledky_evalu](2026-11-22_vysledky_evalu/README.md) | finálne reporty oboch matíc (testing, refactoring) |
| 2026-11-22 | [hlbkova_analyza_evalu](2026-11-22_hlbkova_analyza_evalu/README.md) | typy chýb, nesúhlasné páry, podskupiny, RAG, štatistická sila |
| 2026-11-22 | [ontologia_podla_typu_pripadu](2026-11-22_ontologia_podla_typu_pripadu/README.md) | či ontológia pomohla pri nejakom type prípadu alebo refaktoringu |
| 2026-11-22 | [najcastejsie_chyby](2026-11-22_najcastejsie_chyby/README.md) | najčastejšie chyby základného modelu a FT ramien |
| 2026-11-22 | [adaptery_vo_vahovom_priestore](2026-11-22_adaptery_vo_vahovom_priestore/README.md) | podobnosť LoRA adaptérov s ontológiou a bez nej vo váhach |
| 2026-11-23 | [navrh_slucka_c_d](2026-11-23_navrh_slucka_c_d/README.md) | návrh experimentu iba s dvoma ramenami: opravná slučka bez ontológie (C) a s ontológiou a SHACL (D); zatiaľ nespustený |

Iné miesto v repe pre analýzy a reporty finálnych behov nie je.

### Ďalšie podklady

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
