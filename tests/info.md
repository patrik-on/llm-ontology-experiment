# tests

Automatizované testy pokrývajú:

- YAML config merging a modelové odkazy,
- dataset formátovanie a splitovanie,
- prompt formatting, EOS a label masking,
- direct/RAG/multi-RAG approach kontrakty,
- TestBench a SWE-Refactor adaptéry a direct runner,
- TestBench path safety, dry-run, Maven status a obnova kolidujúceho testu,
- Ollama seed a HTTP error reporting,
- SWE-Refactor whole-file fallback,
- model loader compatibility importy,
- inference helpery, metriky, reportovanie a legacy CLI navigáciu.

Spustenie:

```bash
python -m pytest -q
```

Unit testy nevyžadujú base model, CUDA, plné datasety, Java ani Maven.
Skutočný TestBench Maven canary je samostatný integračný krok z runbooku.
