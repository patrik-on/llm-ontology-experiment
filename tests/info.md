# tests

Testy sú podľa vlastníctva v `datasets/`, `finetuning/`, `retrieval/`,
`inference/`, `evaluation/`, `experiments/` a `ui/`. Cross-area architektonické,
config, import a compatibility kontrakty zostávajú v root `tests/`, aby sa im
nepriradilo zavádzajúce jediné vlastníctvo.

Automatizované testy pokrývajú:

- YAML config merging a modelové odkazy,
- dataset formátovanie a splitovanie,
- prompt formatting, EOS a label masking,
- direct/RAG/multi-RAG approach kontrakty,
- TestBench a SWE-Refactor adaptéry a direct runner,
- TestBench path safety, dry-run, Maven status a obnova kolidujúceho testu,
- Ollama seed a HTTP error reporting,
- SWE-Refactor whole-file fallback,
- handcrafted smoke dataset schema, manifest, hashes, leakage and optional
  JDK/JUnit compilation/behavior integration,
- model loader compatibility importy,
- inference helpery, metriky, reportovanie a legacy CLI navigáciu.

Spustenie:

```bash
python -m pytest -q
```

Unit testy nevyžadujú base model, CUDA ani plné datasety. Smoke integračná
kontrola sa automaticky preskočí, ak lokálny JDK/JUnit Maven cache nie je
dostupný.
Skutočný TestBench Maven canary je samostatný integračný krok z runbooku.
