# Adaptéry vo váhovom priestore (2026-11-22)

Porovnanie štyroch LoRA adaptérov v3 priamo vo váhach (CPU, bez modelu): kosínus
zmeny váh ΔW = BA, normy a podobnosť podpriestorov po vrstvách a moduloch.

**Záver:** adaptér trénovaný s ontológiou je blízko svojho partnera bez nej
(kosínus 0,34 testing, 0,29 refactoring), medzi úlohami je to len 0,015. Ontológia
v tréningu posunie adaptér oveľa menej než zmena úlohy, no nejde o rovnaký adaptér.

- Adaptéry: `b2_testing`, `b2_testing_onto`, `b2_refactoring`, `b2_refactoring_onto`
- Skript: `scripts/analysis/adapter_weight_similarity.py`

| Súbor | Obsah |
|---|---|
| [adapter_weight_similarity.md](adapter_weight_similarity.md) | report s tabuľkami a interpretáciou |
| [adapter_weight_similarity.json](adapter_weight_similarity.json) | čísla po moduloch |
