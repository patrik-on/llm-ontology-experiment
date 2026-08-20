# Legacy frozen Windows environment

> These Windows CPU locks are preserved for provenance only. They are
> `legacy_not_final`; the current experiment runtime is WSL-only and is checked
> with `python -m llm_ontology.env check` inside `.venv_wsl`.

`rag_baseline_windows_cpu.lock.json` is the machine-readable runtime contract.
`requirements-rag-windows-cpu.lock.txt` contains every installed Python package
at the captured version. Validate both with:

```powershell
python scripts/retrieval/check_environment_lock.py
```

The check deliberately fails while the configured Ollama model is absent, its
digest differs, or the Java benchmark toolchain is missing. Use both
`--skip-ollama --skip-benchmark-toolchain` to verify only Python and packages.
