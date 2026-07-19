# Benchmark adapters

Tento balík sprístupňuje vendored `TestBench` a `SWE-Refactor` cez nemenný
`BenchmarkCase` kontrakt. Adaptéry neimportujú pôvodné modelové/API skripty.

- `testbench`: 108 Java test-generation prípadov so source, simple a full
  prompt variantom.
- `swe_refactor`: 1 099 pure Java refactoring prípadov s referenčným výstupom.

TestBench má navyše bezpečný execution planner/evaluator. Nepoužíva hardcoded
Linux cesty, odmieta path traversal, spúšťa Maven bez skladania používateľského
shell príkazu a po každom prípade obnoví pôvodný testovací súbor.
