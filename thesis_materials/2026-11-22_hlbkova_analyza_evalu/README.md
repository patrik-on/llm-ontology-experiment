# Hĺbková analýza evalu (2026-11-22)

Rozbor oboch finálnych behov po ramenách: typy chýb, nesúhlasné páry, podskupiny
prípadov, vplyv dĺžky bloku ontológie, prečo RAG v refaktoringu zlyháva a štatistická
sila (McNemar, Holm, MDE). Iba z uložených výsledkov, bez nových volaní modelu.

- Behy: `testing-matrix-20261122-rag2`, `refactoring-matrix-20261121`
- Skript: `scripts/analysis/deep_analysis.py` (extra `analysis`)

| Súbor | Obsah |
|---|---|
| [deep_analysis.md](deep_analysis.md) | celý report (testing T1–T6, refactoring R1–R5) |
| [deep_analysis_examples.md](deep_analysis_examples.md) | konkrétne príklady výstupov |
| [deep_analysis.json](deep_analysis.json) | všetky čísla strojovo |
