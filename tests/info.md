# tests

Automatizované testy pre:

- YAML config merging a modelové odkazy,
- dataset formátovanie a splitovanie,
- prompt formatting, EOS a label masking,
- direct/RAG/multi-RAG approach kontrakty,
- model loader compatibility importy,
- inference helpery a LoRA detekciu,
- textové metriky a reportovanie,
- legacy CLI navigáciu,
- import všetkých `llm_ontology` modulov.

Spustenie:

```bash
python -m pytest -q
```

Testy nesmú vyžadovať base model, CUDA, plné datasety ani adaptéry. Modelové a
retrieval integračné testy majú používať malé fake alebo dočasné artefakty.
