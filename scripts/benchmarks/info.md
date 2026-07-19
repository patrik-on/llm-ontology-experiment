# Benchmark commands

- `inspect_benchmarks.py`: validácia inventára TestBench a SWE-Refactor.
- `check_readiness.py`: kontrola Maven, JDK matice, Ollama modelu a disk space.
- `run_benchmark.py`: direct prompt-only alebo Ollama generovanie do JSONL.
- `evaluate_testbench.py`: bezpečný TestBench Maven dry-run/compile/test tok.

Odporúčaný postup je readiness check → 1-case generation → evaluation dry-run →
1-case Maven canary → celý benchmark. Detaily sú v
`docs/testbench_runbook.md`.
