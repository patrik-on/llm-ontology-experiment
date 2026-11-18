# Current evaluation

Only two protocols are supported:

| Task | Entry point | Runbook |
|---|---|---|
| Methods2Test testing | `scripts/benchmarks/run_testing_matrix.py` | [Testing](testing_matrix_v1.md) |
| Mixed SWE + MaRV + ML4Ref refactoring | `scripts/benchmarks/run_refactoring_matrix.py` | [Refactoring](refactoring_matrix_v1.md) |

Both compare baseline, FT, Single-RAG, MultiRAG and baseline + existing skill,
with one attempt per case/variant and no repair. Testing defaults to 100 x 5 (500 calls); use `--cases N` for a smaller run.
Refactoring has a released 100-task cohort (5 SWE + 35 MaRV + 60 ML4Ref), with
contextual target-only structural scoring and separate SWE project checks.
N/all and source/type filters use that same fixed cohort. No models have been run.
See the [v4 preparation receipt](refactoring_context_v4_2026-11-13.md).

Both reports include exact paired tests on the same cases: McNemar for
pass/fail outcomes (testing class pass, refactoring structural success) and
Wilcoxon signed-rank for testing coverage credit, with Holm correction across
the ten arm pairs of each metric (`src/llm_ontology/benchmarks/paired_tests.py`).
Cases are convenience-selected and at most ten come from one Methods2Test
project, so p-values are conditional on the selected cases.

All eval outputs belong under `artifacts/evaluation/runs/<run-id>/`. Only the
current testing preparation and refactoring preparation evidence remain. They contain no
model answers. Data/model/index/tool caches and preparation evidence are required
infrastructure, not extra protocols. Older pilot/full/smoke evaluators, entry
points, configs and results have been removed, rather than hidden behind wrappers.

Current implementation and preparation checks: [validation summary](validation_2026-11-13.md).

For research motivation, design choices, metrics and interpretation, read the
[evaluation design report](../../thesis_materials/reports/evaluation_design_2026-11-13.md).
Historical handcrafted skills/AGENTS results are isolated in
[thesis materials](../../thesis_materials/handcrafted_skills/README.md), not in
the active matrix output namespace and not combined with current scores.
