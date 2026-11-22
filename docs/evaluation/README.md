# Current evaluation

Only two protocols are supported:

| Task | Entry point | Runbook |
|---|---|---|
| Methods2Test testing | `scripts/benchmarks/run_testing_matrix.py` | [Testing](testing_matrix_v1.md) |
| Mixed SWE + MaRV + ML4Ref refactoring | `scripts/benchmarks/run_refactoring_matrix.py` | [Refactoring](refactoring_matrix_v1.md) |

Both compare eight arms (`qwen_base`, `onto_project`, `skills`, `skills_onto`,
`rag_single`, `ft_testing`/`ft_refactoring`, `ft_v3_onto`, `ft_onto`), with one attempt
per case/arm and no repair. Testing defaults to 100 x 8 (800 calls); use `--cases N` for a smaller run.
Refactoring has a released 100-task cohort (5 SWE + 35 MaRV + 60 ML4Ref), with
contextual target-only structural scoring and separate SWE project checks.
N/all and source/type filters use that same fixed cohort. The cohort was re-released
on 2026-11-21 (pool run `mixed-context-pool-v5-20261121`, same 100 case IDs as the
[v4 preparation](../archive/evaluation/refactoring_context_v4_2026-11-13.md)) after code and JDK pins changed.
Final runs: testing `testing-matrix-20261122-rag2` (a continuation of
`testing-matrix-20261121` that completed its fail-stopped `rag_single` arm on the same
100 cases; see `continuation.json` in the run) and `refactoring-matrix-20261121`.

Both reports include exact paired tests on the same cases: McNemar for
pass/fail outcomes (testing class pass, refactoring structural success) and
Wilcoxon signed-rank for testing coverage credit, with Holm correction across
the five primary pairs (`primary_pairs` in each matrix JSON) (`src/llm_ontology/benchmarks/paired_tests.py`).
Cases are convenience-selected and at most ten come from one Methods2Test
project, so p-values are conditional on the selected cases.

All eval outputs belong under `artifacts/evaluation/runs/<run-id>/`. The final runs
above contain model answers; their reports are copied to [thesis_materials](../../thesis_materials/README.md), and
the commit each run reports on is listed in the root README. Data/model/index/tool caches and preparation evidence are required
infrastructure, not extra protocols. Older pilot/full/smoke evaluators, entry
points, configs and results have been removed, rather than hidden behind wrappers.

Earlier implementation and preparation checks (2026-11-13): [validation summary](../archive/evaluation/validation_2026-11-13.md).

For research motivation, design choices, metrics and interpretation, read the
[evaluation design report](../../thesis_materials/reports/evaluation_design_2026-11-13.md).
Historical handcrafted skills/AGENTS results are isolated in
[thesis materials](../../thesis_materials/handcrafted_skills/README.md), not in
the active matrix output namespace and not combined with current scores.
